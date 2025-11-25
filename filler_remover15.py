"""
Audio Filler Remover (V5 - Safe Mode Final)
- Highly conservative filler list to protect 'a' and 'and'.
- Explicitly skips 'a' and 'and' in all detection logic.
"""

from faster_whisper import WhisperModel
from pydub import AudioSegment
from pydub.generators import Sine
import torch
import os
import tempfile
import gradio as gr
import gc

# ⚠️ CRITICAL CHANGE: Only core mumbles are kept. 'a', 'and', and 'ah' variants removed.
FILLER_WORDS = {
    'um', 'uh', 'er', 'hmm', 'mhm', 'uh-huh', 'um-hum', 'umm', 'uhh', 'erm', 'ooh'
}

# Add common words to explicitly exclude from any accidental removal.
EXCLUSIONS = {'a', 'and', 'the'}

def transcribe_audio(file_path, model_size='base', device='cpu'):
    compute_type = "float16" if device == "cuda" else "int8"
    print(f"Loading Whisper {model_size} on {device}...")
    
    try:
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        
        prompt = "Umm, uhh, hmm, er, ah, like, you know, I mean, well, right, so"
        
        segments, info = model.transcribe(
            file_path, 
            word_timestamps=True, 
            vad_filter=True,
            initial_prompt=prompt,
            repetition_penalty=1.2
        )
        
        result_segments = []
        for segment in segments:
            words = []
            if segment.words:
                for word in segment.words:
                    words.append({
                        'word': word.word.strip().lower(),
                        'start': word.start,
                        'end': word.end
                    })
            result_segments.append({'words': words})
            
        del model
        gc.collect()
        if device == "cuda":
            torch.cuda.empty_cache()
            
        return result_segments
    except Exception as e:
        raise Exception(f"Transcription failed: {str(e)}")

def find_fillers(segments, filler_list):
    """Finds single filler words (um, ah, etc.) with exclusions."""
    detected = []
    for seg in segments:
        for word in seg['words']:
            clean_word = "".join(c for c in word['word'] if c.isalnum())
            
            # ⛔ Safeguard 1: Explicitly skip common articles/conjunctions
            if clean_word in EXCLUSIONS:
                continue

            if clean_word in filler_list:
                start_ms = int(word['start'] * 1000)
                end_ms = int(word['end'] * 1000)
                detected.append((start_ms, end_ms, clean_word))
    return detected

def find_stutters(segments):
    """Detects repeated adjacent words (stutters) with exclusions."""
    stutters = []
    all_words = []
    for seg in segments:
        all_words.extend(seg['words'])
    
    for i in range(len(all_words) - 1):
        word_a = all_words[i]
        word_b = all_words[i+1]
        
        clean_a = "".join(c for c in word_a['word'] if c.isalnum() or c == '-')
        clean_b = "".join(c for c in word_b['word'] if c.isalnum() or c == '-')

        # ⛔ Safeguard 2: Skip common articles/conjunctions from stutter removal
        if clean_a in EXCLUSIONS:
            continue
            
        if clean_a and clean_a == clean_b:
            start_ms = int(word_a['start'] * 1000)
            end_ms = int(word_a['end'] * 1000)
            
            if (word_b['start'] * 1000 - end_ms) < 200: 
                stutters.append((start_ms, end_ms, f"STUTTER: {clean_a}"))
                
    return stutters

def process_audio_pydub(input_file, output_file, segments_to_remove, debug_beep=False, padding_ms=50, start_offset_ms=100, crossfade_ms=10):
    original_audio = AudioSegment.from_file(input_file)
    duration_ms = len(original_audio)
    
    if not segments_to_remove:
        original_audio.export(output_file, format="mp3")
        return

    segments_time = sorted([(s, e) for s, e, _ in segments_to_remove])
    merged_cuts = []
    for start, end in segments_time:
        start = max(0, start - start_offset_ms)
        end = min(duration_ms, end + padding_ms)
        if merged_cuts and start <= merged_cuts[-1][1]:
            merged_cuts[-1] = (merged_cuts[-1][0], max(merged_cuts[-1][1], end))
        else:
            merged_cuts.append((start, end))

    print(f"Processing {len(merged_cuts)} total segments...")

    if debug_beep:
        processed_audio = original_audio
        for start, end in merged_cuts:
            beep_duration = end - start
            if beep_duration < 1: continue
            beep = Sine(1000).to_audio_segment(duration=beep_duration).apply_gain(-6) 
            processed_audio = processed_audio.overlay(beep, position=start)
    else:
        processed_audio = AudioSegment.empty()
        last_pos = 0
        for start_cut, end_cut in merged_cuts:
            if last_pos < start_cut:
                segment = original_audio[last_pos:start_cut]
                if len(processed_audio) > 0 and crossfade_ms > 0:
                    processed_audio = processed_audio.append(segment, crossfade=crossfade_ms)
                else:
                    processed_audio += segment
            last_pos = end_cut
        
        if last_pos < duration_ms:
            tail = original_audio[last_pos:]
            if len(processed_audio) > 0 and crossfade_ms > 0:
                processed_audio = processed_audio.append(tail, crossfade=crossfade_ms)
            else:
                processed_audio += tail

    out_format = "mp3"
    if output_file.lower().endswith(".flac"): out_format = "flac"
    elif output_file.lower().endswith(".wav"): out_format = "wav"
    
    processed_audio.export(output_file, format=out_format)

def process_gradio(audio, model, pad, lookback, crossfade, custom_words, debug_mode, gpu):
    if not audio: return None, "Please upload a file."
    
    try:
        device = "cuda" if gpu and torch.cuda.is_available() else "cpu"
        
        in_ext = os.path.splitext(audio)[1].lower()
        out_ext = in_ext if in_ext in ['.flac', '.wav', '.mp3'] else '.mp3'
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix=out_ext).name
        
        yield None, "Step 1/3: Transcribing (Final Safety Check)..."
        segments = transcribe_audio(audio, model, device)
        
        fillers_list = set(w.strip().lower() for w in custom_words.split(',')) if custom_words.strip() else FILLER_WORDS
        
        detected_fillers = find_fillers(segments, fillers_list)
        detected_stutters = find_stutters(segments)
        
        detected = detected_fillers + detected_stutters
        
        if not detected:
            yield audio, "No disfluencies found."
            return
            
        action = "BEEPING" if debug_mode else "CUTTING"
        yield None, f"Found {len(detected_fillers)} fillers and {len(detected_stutters)} stutters. Step 2/3: {action} audio..."
        
        process_audio_pydub(audio, output_file, detected, debug_mode, pad, lookback, crossfade)
        
        result_msg = f"Done! {action} {len(detected)} total disfluencies."
        if debug_mode:
            result_msg += "\n(Audio has beeps over detected words. Uncheck 'Debug Mode' to actually remove them.)"
            
        yield output_file, result_msg
        
    except Exception as e:
        yield None, f"Error: {str(e)}"

with gr.Blocks(title="Audio Cleaner Final") as app:
    gr.Markdown("## 🎙️ Audio Cleaner: Final Cut (Maximum Safety)")
    
    with gr.Row():
        with gr.Column():
            inp = gr.Audio(type="filepath", label="Input Audio")
            model = gr.Dropdown(['base', 'small', 'medium', 'large-v2'], value='base', label="Model Accuracy")
            gpu = gr.Checkbox(value=torch.cuda.is_available(), label="Use GPU")
            
            gr.Markdown("### 🛠️ Controls")
            debug = gr.Checkbox(value=True, label="⚠️ Debug Mode (Add Beeps)", info="Checked = Beep (Test Mode). Unchecked = Cut (Final Mode).")
            
            lookback = gr.Slider(0, 300, value=100, step=10, label="Lookback (ms)", info="Set this lower if cuts are too aggressive.")
            pad = gr.Slider(0, 300, value=50, step=10, label="Padding (ms)")
            crossfade = gr.Slider(0, 100, value=10, step=5, label="Crossfade (ms)")
            
            custom = gr.Textbox(label="Custom Words", placeholder="Add specific fillers like 'like' or 'so' HERE.")
            btn = gr.Button("Process Audio", variant="primary")
        
        with gr.Column():
            status = gr.Textbox(label="Status", lines=3)
            out = gr.Audio(label="Result")
            
    btn.click(process_gradio, [inp, model, pad, lookback, crossfade, custom, debug, gpu], [out, status])

if __name__ == "__main__":
    app.launch()

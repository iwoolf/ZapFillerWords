import gradio as gr
import os
from pydub import AudioSegment
import json
import time

# --- Constants and Mock Data ---
# Mock Transcription Data (Word, Start Time (s), End Time (s)).
# In a real application, this would come from a powerful ASR API (e.g., Gemini with ASR, or Whisper)
MOCK_TRANSCRIPT_DATA = [
    {'word': 'Hello,', 'start': 0.10, 'end': 0.50},
    {'word': 'um,', 'start': 0.55, 'end': 0.80},
    {'word': 'this', 'start': 0.90, 'end': 1.20},
    {'word': 'is', 'start': 1.25, 'end': 1.40},
    {'word': 'a', 'start': 1.45, 'end': 1.50},
    {'word': 'test', 'start': 1.55, 'end': 1.90},
    {'word': 'of', 'start': 1.95, 'end': 2.10},
    {'word': 'the', 'start': 2.15, 'end': 2.30},
    {'word': 'filler', 'start': 2.35, 'end': 2.70},
    {'word': 'remover,', 'start': 2.75, 'end': 3.20},
    {'word': 'ah,', 'start': 3.30, 'end': 3.60},
    {'word': 'and', 'start': 3.65, 'end': 3.80},
    {'word': 'you', 'start': 3.85, 'end': 4.00},
    {'word': 'can', 'start': 4.05, 'end': 4.20},
    {'word': 'select', 'start': 4.25, 'end': 4.60},
    {'word': 'words', 'start': 4.65, 'end': 4.90},
    {'word': 'to', 'start': 4.95, 'end': 5.05},
    {'word': 'remove,', 'start': 5.10, 'end': 5.50},
    {'word': 'uh,', 'start': 5.55, 'end': 5.80},
    {'word': 'manually.', 'start': 5.85, 'end': 6.50},
]
# --- Utility Functions ---

def generate_interactive_transcript_html(transcript_data):
    """
    Generates HTML string for the interactive transcript display.
    Each word is wrapped in a span with a data-index attribute for identification.
    """
    html_parts = []
    # Store the full transcript data as a JSON string in a hidden input
    full_transcript_json = json.dumps(transcript_data)
    
    # Hidden input field to store the full transcript data (used for reference)
    html_parts.append(f'<input type="hidden" id="full-transcript-data" value=\'{full_transcript_json}\'>')
    
    # Generate the word spans
    for i, item in enumerate(transcript_data):
        # The 'data-index' is the critical piece of data that JavaScript sends back
        span_html = f'<span class="word-span" data-index="{i}">{item["word"]} </span>'
        html_parts.append(span_html)
        
    return "".join(html_parts)

def generate_blank_output_path(input_path, suffix="_edited"):
    """Creates a unique output path for the processed file."""
    base, ext = os.path.splitext(input_path)
    # Ensure the input path is clean for naming
    clean_base = os.path.basename(base)
    return f"{clean_base}{suffix}{ext}"

# --- Main Logic Functions ---

def transcribe_and_display(audio_file):
    """
    Simulates transcription and prepares the interactive interface.
    """
    if audio_file is None:
        return "Please upload an audio file first.", None, gr.update(interactive=False)

    # In a real app, ASR generates MOCK_TRANSCRIPT_DATA here
    transcript_html = generate_interactive_transcript_html(MOCK_TRANSCRIPT_DATA)
    original_audio_path = audio_file.name 
    
    # Return the interactive HTML, the original path, and enable the process button
    return transcript_html, original_audio_path, gr.update(interactive=True)

def process_edited_audio(original_audio_path, selected_indices_json):
    """
    Processes the audio by removing the segments corresponding to selected words (indices).
    """
    if original_audio_path is None:
        return None, "Error: No original audio file found to process."

    try:
        # 1. Parse the selected indices returned by JavaScript
        selected_indices = {int(i) for i in json.loads(selected_indices_json)}
    except json.JSONDecodeError:
        return None, "Error: Could not parse selected words."
    
    # Use the mock transcript data for the timestamps
    transcript = MOCK_TRANSCRIPT_DATA 
    
    # 2. Load the audio file using pydub
    try:
        audio = AudioSegment.from_file(original_audio_path)
    except Exception as e:
        return None, f"Error loading audio file: {e}"

    # 3. Create the new audio segment by concatenation
    new_audio = AudioSegment.empty()
    last_kept_end_ms = 0 # Track the end time of the last kept audio segment

    for i, item in enumerate(transcript):
        start_ms = int(item['start'] * 1000)
        end_ms = int(item['end'] * 1000)
        
        if i in selected_indices:
            # Word is marked for removal. 
            # We skip the segment (start_ms to end_ms), but we need to track 
            # where the audio should continue from. The audio should stop at 
            # last_kept_end_ms and resume at the end of the removed word (end_ms).
            pass
        else:
            # Word is to be kept.
            
            # Keep the silent gap (from last_kept_end_ms to current word start)
            silent_gap = audio[last_kept_end_ms:start_ms]
            
            # Keep the word itself (from current word start to current word end)
            word_segment = audio[start_ms:end_ms]
            
            new_audio += silent_gap
            new_audio += word_segment
            
            # Update the point where the next segment should start from
            last_kept_end_ms = end_ms 

    # If there's audio remaining after the last word, append it
    if last_kept_end_ms < len(audio):
        new_audio += audio[last_kept_end_ms:]


    # 4. Save the final processed audio
    output_path = generate_blank_output_path(original_audio_path, "_edited")
    new_audio.export(output_path, format="mp3") # Export as MP3 for compatibility

    # 5. Generate a simple text log of what was removed
    removed_words = [transcript[i]['word'] for i in selected_indices]
    
    if not removed_words:
        log_message = "No words were selected for removal. Original audio logic applied (though no changes were made)."
    else:
        log_message = f"Successfully removed the following segments (words selected by user): {', '.join(removed_words)}"
    
    return output_path, log_message

# --- Gradio Interface Setup ---

# Define the custom JavaScript for interaction
INTERACTIVE_JS = """
function setupTranscriptInteraction() {
    const transcriptContainer = document.getElementById('transcript-output');
    if (!transcriptContainer) return;

    // Hidden input to store selected indices (JSON string) - linked to gr.Textbox
    const selectedInput = document.getElementById('selected-indices-json');
    
    // Use a Set for efficient tracking of selected indices
    let selectedIndices = new Set();
    
    // Function to update the hidden input field which Gradio reads
    const updateSelectedInput = () => {
        // Convert Set to Array before stringifying for JSON compatibility
        selectedInput.value = JSON.stringify(Array.from(selectedIndices));
        // Trigger Gradio's event to update the component state
        selectedInput.dispatchEvent(new Event('input', { bubbles: true }));
    };

    // Attach click listener to the main container
    transcriptContainer.addEventListener('click', function(event) {
        const target = event.target;
        if (target.classList.contains('word-span')) {
            const index = parseInt(target.getAttribute('data-index'));
            
            if (target.classList.contains('selected')) {
                // Deselect
                target.classList.remove('selected');
                selectedIndices.delete(index);
            } else {
                // Select
                target.classList.add('selected');
                selectedIndices.add(index);
            }
            updateSelectedInput();
        }
    });
    
    // Initial update in case of pre-filled data (for completeness)
    updateSelectedInput();
}

// Gradio hook to run JS after the interface loads/updates
// Use a timeout to ensure the DOM elements are fully rendered by Gradio
setTimeout(setupTranscriptInteraction, 500); 
"""

with gr.Blocks(title="🎙️ Interactive Audio Editor") as demo:
    gr.HTML("""
        <div class="text-center p-4 bg-indigo-50 rounded-lg shadow-md">
            <h1 class="text-3xl font-extrabold text-indigo-800">Interactive Audio Editor</h1>
            <p class="text-gray-600 mt-2">Upload your audio, get the transcript, and click words you want to remove.</p>
        </div>
    """)
    
    # Hidden state to pass the original audio path across functions
    original_audio_path_state = gr.State(None)

    # Hidden input linked to a Gradio Textbox component, used by JS to pass data to Python
    selected_indices_input = gr.Textbox(
        label="Selected Indices (JSON)", 
        visible=False, 
        elem_id="selected-indices-json",
        value="[]"
    )

    with gr.Row():
        with gr.Column(scale=1):
            audio_input = gr.File(label="1. Upload Audio File (e.g., MP3, WAV)", file_types=[".mp3", ".wav", ".flac"])
            
            # Button to trigger transcription
            transcribe_btn = gr.Button("2. Transcribe & Prepare for Editing", variant="primary")
            
            # Area for the interactive transcript
            transcript_output = gr.HTML(
                label="3. Interactive Transcript (Click words to mark for removal)", 
                elem_id="transcript-output",
                value="<p class='text-gray-500'>Upload and Transcribe audio to see the transcript here.</p>"
            )

        with gr.Column(scale=1):
            # Button to trigger final processing (editing)
            process_btn = gr.Button("4. Remove Selected Words & Generate New Audio", variant="secondary", interactive=False)
            
            audio_output = gr.Audio(label="5. Edited Audio Output (MP3 Format)")
            log_output = gr.Textbox(label="Processing Log", lines=3, interactive=False)
            
            gr.HTML("""
                <div class="mt-4 p-2 bg-blue-100 border border-blue-300 rounded-md text-sm text-blue-800">
                    <p><strong>Note:</strong> This version uses mock word-level timestamps for demonstration. The interactive selection and audio manipulation logic are fully functional based on this mock data. The output is saved as MP3.</p>
                </div>
            """)

    # --- Flow Logic ---
    
    # 1. User uploads file and clicks Transcribe
    transcribe_btn.click(
        fn=transcribe_and_display,
        inputs=[audio_input],
        outputs=[transcript_output, original_audio_path_state, process_btn],
    )
    
    # 2. User interacts with transcript and clicks Process
    process_btn.click(
        fn=process_edited_audio,
        inputs=[original_audio_path_state, selected_indices_input],
        outputs=[audio_output, log_output]
    )

# Add custom CSS and JavaScript for the interactive transcript styling and logic
# Gradio automatically wraps the JS code in a script tag.
demo.load(js=INTERACTIVE_JS) 

# Custom CSS for the interactive transcript styling
demo.css = """
/* Custom font, using system defaults with Inter as preference */
.gradio-container {
    font-family: 'Inter', sans-serif;
}
/* Styles for the interactive transcript container */
#transcript-output {
    min-height: 200px;
    max-height: 400px;
    overflow-y: auto;
    padding: 15px;
    border: 1px solid #d1d5db;
    border-radius: 12px;
    line-height: 1.8;
    user-select: none; 
    background-color: #ffffff;
    font-size: 1.1em;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}
.word-span {
    cursor: pointer;
    padding: 2px 4px;
    margin: 0 1px;
    border-radius: 6px;
    transition: background-color 0.2s, color 0.2s, opacity 0.2s;
    display: inline-block;
    color: #1f2937; /* Dark text */
}
.word-span:hover {
    background-color: #c7d2fe; /* Light indigo hover */
    color: #1e3a8a;
}
.word-span.selected {
    background-color: #ef4444; /* Red for removal */
    color: white;
    font-weight: 600;
    text-decoration: line-through;
    opacity: 0.8;
}
"""

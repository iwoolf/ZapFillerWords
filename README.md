# ZapFillerWords
🎙️ Audio Filler Remover: Setup and Run Guide

Identify and remove filler words from media, using vibe coding

This project doesn't work yet. It successfully finds ums, and either removes them or plays a tone over them. Currently when audio is transcribed, the a, and, at etc are detected as ah, and beeped.
This is a transcription problem. It may be helpful to see the transcription to see where its going wrong, as a next step to debugging.
Audio is uploaded in a gradio web interface. The audio is transcribed with timestamps for each word. The transcript is searched for filler words like um and ah. Pydub is used to edit the source audio at the points where filler words are detected. There may be a better way to do this.

This guide details how to set up the Python environment, install dependencies, and run the filler_remover script (which uses gradio to provide a user interface).

⚠️ Prerequisites

Python 3.10+: Ensure Python is installed on your system. Crucially, make sure the box "Add python.exe to PATH" was checked during installation.

FFmpeg: This system dependency is required by the pydub library for audio processing. You must install FFmpeg and ensure its binaries are accessible via your system's PATH.

🚀 1. Setup Environment (PowerShell)

It is highly recommended to use a virtual environment (venv) to keep project dependencies isolated.

Navigate to the Project Folder:
Open PowerShell and use the cd command to navigate to the root directory where you downloaded this code (e.g., fillerZapper).

cd fillerZapper


Create the Virtual Environment:
This command creates a new environment named venv in your project folder.

python -m venv venv


Activate the Environment:
You may need to bypass PowerShell's execution policy for this session only to run the activation script.

# 3a. Bypass execution policy (if necessary)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 3b. Activate the environment
.\venv\Scripts\Activate.ps1


Your prompt should now be prefixed with (venv), confirming activation: (venv) G:\fillerZapper>

📦 2. Install Dependencies

With the environment active, install all required packages listed in requirements.txt.

pip install -r requirements.txt


▶️ 3. Run the Application

Once dependencies are installed, you can start the Gradio web application.

python .\filler_remover15.py


This will start a local server and provide a URL (usually http://127.0.0.1:7860) that you can open in your web browser to use the audio cleaner interface.

🛑 4. Deactivate Environment

When you are done working on the project, you can exit the virtual environment:

deactivate

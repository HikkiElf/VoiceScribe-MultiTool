# VoiceScribe-MultiTool

VoiceScribe-MultiTool is a powerful, desktop-centric local application for real-time speech-to-text recording, audio transcription, and speaker diarization. It integrates state-of-the-art offline models, specifically **GigaAM-v3 RNNT** and **WhisperX** (with PyAnnote), to process Russian and English audio entirely locally on your machine.

---

## Architecture Overview (MVC)

The project has been refactored into a clean Model-View-Controller (MVC) architecture for better maintainability, testability, and separation of concerns:

- **Model** (`src/backend/model.py`): Manages and stores the application state, configuration details, paths, and token settings.
- **View** (`src/frontend/view.py`): Renders the PyQt6 desktop user interface, establishes QSS layouts, and exposes interactive components.
- **Controller** (`src/frontend/controller.py`): Handles the application's business logic, hooks UI widget events, and runs background worker threads.
- **Workers** (`src/backend/workers.py`): Runs the processing tasks (GigaAM transcribing, PyAnnote diarization, and WhisperX post-processing) on background threads to keep the UI responsive.

---

## Features

1. **🎙️ Live Recording (GigaAM):** Stream real-time audio from your microphone, automatically segment on silence thresholds, transcribe chunks on-the-fly, and save the full master audio.
2. **👥 Diarization & Separation (GigaAM + PyAnnote):** Process pre-recorded files, automatically partition turns using PyAnnote VAD/Embeddings, extract voice segments, transcribe them locally, and log speaker names with exact timing tags.
3. **👥 Diarization & Separation (WhisperX):** Run local diarization workflows using WhisperX large-v3 models, supporting automatic exports to `TXT`, `SRT`, `TSV`, `JSON`, and `VTT` formats.

---

## Prerequisites

To run this application locally, you must meet the following system requirements:

1. **Python 3.10** (Recommended version matching the development environment).
2. **FFmpeg**: Required for audio segment processing and slicing.
   - **macOS (Homebrew):** `brew install ffmpeg`
   - **Windows (Chocolatey):** `choco install ffmpeg` (or download from official site and add to your System PATH).
3. **Hugging Face Account & Token**: Required to download the PyAnnote speaker diarization models.

---

## Installation & Setup

Follow these steps to set up the environment and run the application:

### 1. Set Up Virtual Environment

Open your terminal and navigate to the project directory:

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows (cmd):
venv\\Scripts\\activate.bat
# On Windows (Powershell):
.\\venv\\Scripts\\Activate.ps1
```

### 2. Install Python Dependencies

Install the required packages listed in the `requirements.txt`:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Hugging Face Token for Diarization

The diarization models are hosted on Hugging Face. You must request access to the models and generate a token:

1. Visit Hugging Face, sign in, and accept the user agreements for:
   - [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)
   - [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
2. Go to your Hugging Face account settings under **Access Tokens** and create a **Read** token.
3. You can paste this token directly into the **Hugging Face Token** input at the top of the GUI interface and click **Сохранить в .env**.

---

## How to Run

### Running in GUI Mode (PyQt6 Desktop Interface)

Launch the interactive desktop interface:

```bash
python src/main.py
```

### Running in CLI Mode (Command Line Interface)

You can also run speaker diarization directly from your terminal using the helper CLI script:

```bash
python diarize.py -i <path_to_audio_file> -o <output_txt_file> --token <your_hf_token>
```

#### Optional CLI arguments:
- `--min-speakers <int>`: Minimum number of speakers in the audio.
- `--max-speakers <int>`: Maximum number of speakers in the audio.
- `--num-speakers <int>`: Exact number of speakers (overrides min/max limits).

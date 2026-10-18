# Setup

## Install From Source

1. Install Python 3.10 or 3.11.
2. Clone or download Waky.
3. Open PowerShell in the Waky folder.
4. Create and activate a virtual environment:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

5. Run:

```powershell
run.bat
```

For daily hidden launch:

```powershell
.\start_waky_hidden.vbs
```

## Hotkeys

- Ctrl+Win: push-to-talk dictation and smart selected text rewrite.
- F8: backup push-to-talk.
- F9: toggle recording.
- Esc: cancel/reset.

## First Run

If no cloud key is configured, use local transcription:

- Settings -> Transcription -> Backend -> Local faster-whisper
- Local model: base

The first local model use can take longer while dependencies/model cache are prepared.

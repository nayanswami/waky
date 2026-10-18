# Waky

Waky is a Windows AI voice dictation and writing assistant. Hold a hotkey, speak naturally, and Waky transcribes, cleans, rewrites, and pastes polished text into the active text field.

Waky is designed for normal Windows apps and browser text boxes: Gmail, WhatsApp Web, Notion, ChatGPT, editors, docs, and forms.

## Features

- Push-to-talk dictation with Ctrl+Win and F8 backup.
- Hands-free toggle mode with F9.
- Esc cancel/reset.
- Floating always-on-top status indicator.
- Paste into the active field without pressing Enter.
- Selected text rewrite mode when text is selected before dictating.
- Voice commands such as write email, bullet points, prompt mode, professional tone, casual tone, rewrite and humanizer, and extend.
- Local/offline transcription with faster-whisper.
- Optional BYOK cloud transcription/rewrite, currently Groq-first.
- Local memory, vocabulary, snippets, and correction files.
- Privacy-first defaults: no audio recordings are saved.

## Requirements

- Windows 11 recommended.
- Python 3.10 or 3.11.
- A working microphone.
- Optional NVIDIA GPU for local acceleration.
- Optional API key for cloud mode.

## Quick Start From Source

```powershell
cd "C:\path\to\waky"
py -3.11 -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
run.bat
```

For normal hidden startup after setup:

```powershell
.\start_waky_hidden.vbs
```

## Basic Usage

1. Start Waky.
2. Click any text field.
3. Hold Ctrl+Win or F8.
4. Speak.
5. Release the hotkey.
6. Waky transcribes and pastes the result.

Selected text rewrite:

1. Select text in any app.
2. Hold Ctrl+Win.
3. Say an instruction such as "make it professional and extend".
4. Release.
5. Waky replaces the selected text.

## Bring Your Own Key

No API keys are included. Users must provide their own keys if they want cloud features.

Waky can run in local/offline mode without an API key. Cloud mode can improve transcription or rewriting depending on provider availability.

See [docs/BYOK.md](docs/BYOK.md).

## Local Mode

Local mode uses faster-whisper. Models are not committed to this repository. They are downloaded/cache-managed by the underlying libraries on first use.

See [docs/LOCAL_MODELS.md](docs/LOCAL_MODELS.md).

## Build the installer

Requirements: Windows, Python 3.11, and [Inno Setup 6](https://jrsoftware.org/isinfo.php) (optional, for the installer).

```powershell
scriptsuild_windows.ps1
```

Output:

- `dist\Waky\Waky.exe` (portable folder, no console window)
- `dist\installer\Waky-Setup-<version>.exe` (when Inno Setup is installed)

Installed builds keep your settings, logs and memory in `%APPDATA%\Waky`, and API keys in Windows Credential Manager. Uninstalling keeps that data. Set `WAKY_DATA_DIR` to use another folder (portable use).

## Privacy

- Waky does not save raw audio recordings.
- Logs are local.
- Memory/snippets/config are local files.
- Cloud providers receive text or audio only when you enable/configure cloud features.
- Do not commit your `.env`, `config/settings.json`, logs, memory, or build output.

## Screenshots

Screenshots are not included yet. Add public-safe screenshots under `docs/assets/` later.

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## License

MIT License. See [LICENSE](LICENSE).

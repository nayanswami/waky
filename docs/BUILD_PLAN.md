# Waky v1 — Build Plan

Base: existing Python + PySide6 app (extracted from `Waky-Full-2026-09-30.zip`, without `.venv`, `.git`, personal `config/settings.json`, `memory/`, `logs/`).
Target: Windows `.exe` installer, downloadable from a Netlify-hosted site. BYOK (Groq first). Local Whisper as optional fallback.

## What already works (keep, do not break)
- Push-to-talk (Ctrl+Win / F8), toggle (F9), Esc cancel — `app/hotkeys.py`
- Record -> transcribe (Groq or local faster-whisper) -> paste — `app/transcriber.py`, `app/clipboard_inserter.py`
- Selected-text rewrite via smart hotkey — `app/selected_text_rewriter.py`
- Floating bar + tray — `app/ui_floating_bar.py`
- Local memory / vocabulary / snippets — `app/local_memory.py`

## Gaps vs. the goal
| Gap | Today | Needed |
|---|---|---|
| Rewrite quality | `command_rewrite_engine: rule_based` (60 KB of templates in `command_processor.py`); Groq chat is optional | LLM-first engine (Groq `llama-3.3-70b-versatile`), rules only as offline fallback |
| Custom instructions | Fixed command list + `custom_commands.json` trigger phrases | **Modes**: user-defined name + trigger phrase + instruction prompt (email, bullets, blog, prompt...). Also free-form spoken instructions |
| API key storage | Plain text in `settings.json` | Windows Credential Manager (`keyring`) |
| Onboarding | None | First-run wizard: welcome -> Groq key guide (link + steps) -> mic test -> hotkey pick -> pill style -> try it |
| Fallback | `auto_fallback` exists for transcription | On Groq 429/limit: switch to local Whisper (optional model download with progress), notify user, auto-return |
| Hotkey choice | Config file only | Hotkey recorder in settings |
| Pill designs | One look | 3-4 selectable styles, saved in settings |
| Settings access | Tray / bar | Hover on bar shows gear -> opens settings (exists via `settings_requested`, restyle) |
| Autostart | `.vbs` launcher | Registry Run key from packaged exe, no console |
| Packaging | `build_windows.bat` | PyInstaller (windowed) + Inno Setup installer |
| Website | None | Netlify landing page + download button + setup guide |

## Phases
1. **Rewrite engine** — new `app/llm_engine.py`: Groq chat client, system prompt = "understand and rewrite, output only final text", inputs = transcript + selected text + active mode + memory/vocab. Rules engine becomes fallback.
2. **Modes + custom instructions** — mode store (`config/modes.json`), UI to add/edit, voice trigger ("convert into mail"), default mode.
3. **Key + fallback** — keyring storage, Groq 429 handling, local Whisper download manager.
4. **Onboarding wizard + hotkey picker + pill styles**.
5. **Packaging** — PyInstaller + Inno Setup, autostart, versioned release.
6. **Website** — Netlify site, download link (GitHub Releases or Netlify asset), setup guide.

## Safety notes
- Never ship `config/settings.json` or `memory/` (the zip contains the author's real ones; excluded here). Rotate the Groq key if that zip was ever shared.
- No default API key anywhere.

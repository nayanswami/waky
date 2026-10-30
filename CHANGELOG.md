# Changelog

## 1.4.4

- Fixed the real cause of YouTube and music sounding different: when Windows' default microphone is a Bluetooth headset, dictating switched the earbuds to low-quality call sound. Automatic microphone now uses the built-in or wired microphone instead (pick a microphone in Settings > Audio to override).

## 1.4.3

- Fixed: while Waky was running, YouTube, music and Bluetooth headphones could sound different (like a call was active) until Waky was quit. Waky kept the microphone open all day; it now opens it only while you hold the dictation key. "Instant start" in Settings > Audio brings the old behaviour back.

## 1.4.2

- Fixed the orange icon: the build was replacing the Waky logo. The taskbar, tray and installer use the blue logo again.
- Hover the pill and a Settings button slides out.
- What's new screen after an update (also under Settings > Updates).
- Learn from my fix: select a corrected sentence and press Ctrl+Alt+L so Waky remembers what you meant.

## 1.4.1

- Opening Waky again (Start menu, desktop shortcut, double-click) now brings up its Settings window instead of saying it is already running.

## 1.4.0

- New Insights page in Settings: words per minute, fixes made by Waky, total words dictated, day streak with a heatmap, where you dictate, and your catchphrase, most used and most corrected words.
- Insights keeps counts only on your PC (no audio, no full text) and can be reset any time.

## 0.1.0

- Initial public-ready Waky source copy.
- Preserves dictation, selected text rewrite, command processing, snippets, local memory, and BYOK Groq support from the original private project.
- Adds public docs, build scripts, GitHub Actions workflow, and sanitized example config.

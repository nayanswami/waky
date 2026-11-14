# Changelog

## 1.4.5

- No more phantom "Thank you": Whisper's silence phrases ("Thank you.", "Thanks for watching") are dropped, even on a silent recording.
- Waky now learns from your edits by itself. Fix a word in what Waky just pasted and it saves the fix and shows a notice. Turn it off in Settings > History. Ctrl+Alt+L still works.
- Smart language: English stays English, Hindi is written as Hinglish. Choose Hinglish, English or Hindi script in Settings > Transcription.
- Style learning: Waky notices whether you end messages with a full stop or start with a capital, and follows your habit.
- Snappier: short phrases skip the AI cleanup and the connection to Groq is kept warm.
- More precise punctuation: question marks, commas after openers and before "but", capital I, final full stop.
- New pill animations that follow your voice. Results show on the pill's own dots (green wave for pasted, red for an error). Choose Fluid, Playful, Calm or Minimal and a Snappy to Buttery slider in Settings > Floating Bar.
- New Waky-style notification cards (can be turned off in Settings > General).
- Insights: real app names, busiest hours, typing time saved, weekly words, average dictation, longest dictation and a summary. The pixel banner is gone from that page.

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

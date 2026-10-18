# Troubleshooting

## Nothing happens when I press the hotkey

- Check that Waky is running in the tray.
- Try F8 as the backup push-to-talk key.
- Open Settings -> Diagnostics -> Hotkey Test.
- Some elevated/admin apps may require Waky to run with similar privileges.

## Microphone fails

Open Windows Settings:

`Privacy & security -> Microphone`

Turn on:

1. Microphone access
2. Let apps access your microphone
3. Let desktop apps access your microphone

Then use Settings -> Audio -> Microphone Test.

## Cloud API fails

If you see 401, 403, quota, or network errors:

- Check the API key.
- Check provider quota/billing.
- Check your internet connection.
- Switch to Local faster-whisper mode.

Waky should not crash if a cloud provider is missing or fails.

## Local transcription is slow

- Use model `base` for fastest testing.
- Use CPU safe mode if CUDA causes problems.
- Close heavy GPU applications.

## Paste does not work

- Test in Notepad first.
- Make sure the target text field is focused.
- Waky never presses Enter automatically.

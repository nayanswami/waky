# Bring Your Own Key

Waky does not ship with API keys. Cloud features require your own provider key.

## Supported Today

### Groq

Groq is supported for speech-to-text and optional command rewriting.

Environment variable:

```env
GROQ_API_KEY=your_key_here
```

Settings UI:

`Settings -> Privacy -> Provider -> groq -> Groq API key`

Recommended transcription model:

- `whisper-large-v3-turbo` for speed
- `whisper-large-v3` for accuracy

## Provider Placeholders

OpenAI and OpenRouter provider fields are included for future extension and rewrite/chat use. If they are not configured or not implemented for a path, Waky should fall back safely rather than crash.

Environment variables:

```env
OPENAI_API_KEY=
OPENROUTER_API_KEY=
```

## Security Notes

- Never commit `.env`.
- Never commit `config/settings.json` if it contains keys.
- Prefer local/offline mode when privacy matters most.
- Cloud transcription sends audio to the chosen provider.
- Cloud rewriting sends text to the chosen provider.

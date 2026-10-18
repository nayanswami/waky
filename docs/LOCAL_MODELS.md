# Local Models

Waky uses faster-whisper for local/offline transcription.

## Models

Common local model choices:

- `base`: fastest and best for first-time testing.
- `small`: balanced.
- `medium`: better accuracy, slower.
- `large-v3`: most accurate local option, heavier.

## Model Storage

Model files are not included in this repository. They are downloaded/cache-managed by the underlying libraries on first use.

Do not commit model files. They can be large and may have separate license terms.

## Recommended Public Defaults

For beginner-friendly local mode:

- Backend: Local faster-whisper
- Model: base
- Engine mode: Safe CPU
- Compute type: int8

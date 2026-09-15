# Media File Tools

Scripts for processing files received via any transport (Telegram, Matrix, API).

## Common Commands

```bash
python3 tools/media_tools/list_files.py --limit 20
python3 tools/media_tools/list_files.py --type image
python3 tools/media_tools/list_files.py --date 2026-01-15
python3 tools/media_tools/file_info.py --file /absolute/path/to/file
python3 tools/media_tools/read_document.py --file /absolute/path/to/doc.pdf
python3 tools/media_tools/transcribe_audio.py --file /absolute/path/to/audio.ogg
python3 tools/media_tools/process_video.py --file /absolute/path/to/video.mp4
```

## File-Type Routing

- image/photo: inspect directly
- audio/voice: transcribe first
- document/PDF: extract text
- video: frames + transcript
- sticker: acknowledge naturally

## Image Generation

Generate an image with the configured image provider, whatever model you run on:

```bash
patchbay image "<detailed prompt>" --out /absolute/path/to/output_to_user/<name>.png
patchbay image "<prompt>" --out <path> --model <model> --size 1024x1024 --overwrite
```

- `--model` and `--size` are optional. Without them the configured default model and the provider's default size apply.
- The command prints the saved path. The suffix follows the returned format and can differ from `--out`, so use the printed path.
- It never replaces an existing file unless `--overwrite` is passed. Pass it only when the user wants the file replaced.
- Do not open, read or inspect a generated image yourself. Send it with `<file:/absolute/path>` and ask the user to confirm it visually. Inspect it yourself only when the user has explicitly allowed you to check outputs on your own.
- On a configuration error, tell the user what to set: the key in `/settings` → API keys → Image generation, and `IMAGEGEN_BASE_URL` / `IMAGEGEN_MODEL` in `~/.phoenix-patchbay/.env`. Never look for keys or call an image API directly.
- Not available inside Docker sandbox mode.

## Dependencies

- always available: `file_info.py`, `list_files.py`
- PDF parsing: `pypdf`
- YAML listing: `pyyaml`
- audio transcription: OpenAI API key or local Whisper variants
- video processing: `ffmpeg`

## Response UX

After processing, offer concise next actions (optional buttons) when helpful.

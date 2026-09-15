# Image generation (`patchbay image`)

## Goal

Let any agent patchbay runs generate an image through an OpenAI-compatible image API,
whatever model the agent itself runs on, without the API key ever entering the agent's
environment, prompt or transcript. Provider-agnostic: OpenAI, 9router, Together or any
service that serves `POST /images/generations`.

## Decisions

- API keys are controlled from `/settings` only. No environment fallback for keys.
- The 9router key follows the same rule: `NINEROUTER_API_KEY` is removed from the
  environment lookup, `deploy/compose.yaml`, `deploy/.env.example`, docs and tests.
  No migration; the project has no users yet, so this is a clean break noted in docs.
- Endpoints and models stay in the environment (process env or
  `~/.phoenix-patchbay/.env`): `IMAGEGEN_BASE_URL`, `IMAGEGEN_MODEL`.
- Paid keys are allowed on the settings screen. The settings module docstring and the
  README say to use a dedicated key with a spending cap set at the provider.
- No user-specific defaults in the repo: no model name, no size.
- Agents never open a generated image on their own. They send it to the user and ask
  for visual confirmation, unless the user explicitly allowed them to inspect output.

## Configuration

| What | Where | Name |
|---|---|---|
| Image API key | `/settings` → API keys → Image generation | `imagegen_api_key` in `config.json` |
| 9router API key | `/settings` → API keys → 9router | `ninerouter_api_key` in `config.json` |
| Image API base URL | env or `~/.phoenix-patchbay/.env` | `IMAGEGEN_BASE_URL`, OpenAI style, including `/v1` |
| Default image model | env or `~/.phoenix-patchbay/.env` | `IMAGEGEN_MODEL` |

`imagegen` rather than `image`, because `config.image` already configures incoming image
processing, and `IMAGE_*` reads like a Docker image variable.

Key check on save and on "Test": `GET {IMAGEGEN_BASE_URL}/models` with the key.
401/403 rejects, 200 accepts, anything else or a network error saves nothing and says the
service is unreachable. No URL configured gives a dedicated message. Limitation, documented:
a provider whose model list is public accepts any key; the first real call exposes it.

## Command

```
patchbay image "<prompt>" --out PATH [--model M] [--size WxH] [--overwrite]
```

1. Resolve the key from `config.json` on disk (so a rotation applies on the next call),
   the URL and model from the environment, `--model` overriding `IMAGEGEN_MODEL`.
   Anything missing: exit 1 with a message naming the setting to fix.
2. `POST {base}/images/generations` with `model`, `prompt`, `n: 1`, and `size` only when
   given. Never `response_format` (gpt-image models reject it). Timeout 180 s.
3. Accept `data[0].b64_json` (decode) or `data[0].url` (download without the
   `Authorization` header, so the key never reaches a third-party host).
4. Choose the file suffix from the bytes (PNG, JPEG, WebP), falling back to `--out`'s.
   Refuse to replace an existing file unless `--overwrite`. Create parent directories.
5. Print only the saved path. Errors go to stderr, never contain the key, exit 1.

The command does not approve the file for the read-guard hook.

## Components

- `phoenix_patchbay/cli/imagegen.py`: `settings()`, `verify_api_key()`, `generate()`.
- `phoenix_patchbay/cli_commands/image.py`: argument parsing, exit codes.
- `phoenix_patchbay/__main__.py`: `image` in the command table.
- `phoenix_patchbay/config.py`: `imagegen_api_key` field, null normalisation.
- `phoenix_patchbay/orchestrator/selectors/settings_selector.py`: new `Setting` row;
  docstring rule rewritten for paid, capped keys.
- `phoenix_patchbay/cli/ninerouter.py`: key only from `config.json`.
- `phoenix_patchbay/i18n/*/chat.toml`: strings for the new row in every locale.

## Agent and user documentation

- `workspace/tools/media_tools/RULES.md`: "Image generation" section. Command and flags;
  the printed path may differ in suffix; save user deliverables under `output_to_user/`
  and send with `<file:...>`; do not open the image, ask the user to confirm it visually,
  unless they explicitly allowed self-checking; on a configuration error tell the user
  what to set and never look for keys or call providers directly. No style rules.
- `workspace/RULES.md` Tool Routing: media_tools line mentions image generation.
- `README.md` and `deploy/README.md`: setup, capped-key advice, key check limitation,
  9router key now set in `/settings`, not available inside `docker_container` sandboxes.
- `deploy/compose.yaml`, `deploy/.env.example`: drop `NINEROUTER_API_KEY`, add
  `IMAGEGEN_BASE_URL` and `IMAGEGEN_MODEL` passthrough.

## Testing

- `tests/cli/test_imagegen.py` against a local `http.server` provider: b64 response
  (suffix from bytes, overwrite refused, no read-guard approval written), url response
  (downloaded, no `Authorization` sent to the download host), `size` omitted when not
  given, missing key/URL/model errors, key check 200/401/no URL.
- `tests/cli/test_ninerouter.py`: an environment key is ignored.
- Settings selector and i18n tests updated as needed.
- Full `pytest`, `ruff check`, `ruff format --check`, `mypy`; one live call against a real
  router with a throwaway patchbay home.

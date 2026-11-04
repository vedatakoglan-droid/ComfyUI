---
name: comfyui
description: Run and automate ComfyUI (node-based Stable Diffusion / image, video and audio generation). Use when the user wants to start a ComfyUI server, run or batch a workflow from the command line or Python, change prompts/seeds in a workflow, upload input images, or fetch generated outputs.
---

# ComfyUI

ComfyUI is a node-graph engine for diffusion models with an HTTP + WebSocket API (default `http://127.0.0.1:8188`).

## 1. Start the server

```bash
cd ComfyUI
pip install -r requirements.txt          # once, inside a venv
python main.py                           # http://127.0.0.1:8188
```

Useful flags (`comfy/cli_args.py`):

| Flag | Purpose |
|---|---|
| `--listen` | Listen on all interfaces (default 127.0.0.1) |
| `--port 8188` | Change port |
| `--disable-auto-launch` | Don't open a browser |
| `--output-directory DIR` / `--input-directory DIR` | Custom folders |
| `--lowvram` / `--highvram` / `--cpu` | Memory / device modes |
| `--enable-cors-header` | Allow calls from other origins |

Check it is up: `curl -s http://127.0.0.1:8188/system_stats`.

Models go under `models/` (`checkpoints/`, `loras/`, `vae/`, `controlnet/`, `upscale_models/`, ...). List what the server sees: `curl -s http://127.0.0.1:8188/models/checkpoints`.

## 2. Get a workflow in API format

The API needs the **API format** (a dict of `node_id -> {class_type, inputs}`), not the UI file with `nodes`/`links`.
In the ComfyUI web UI: **Workflow → Export (API)**. Keep it as `workflow_api.json`.

```json
{
  "3": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 20, "model": ["4", 0], "...": "..."}},
  "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "a cat", "clip": ["4", 1]}}
}
```

`["4", 0]` means "output 0 of node 4". Find which node holds the prompt/seed by its `class_type`.

## 3. Run it

Use the bundled script (stdlib only):

```bash
python scripts/run_workflow.py workflow_api.json \
  --set 6.text="a red fox in snow, cinematic" \
  --set 3.seed=42 --out outputs
```

It POSTs to `/prompt`, polls `/history/{prompt_id}` until done, and downloads every output via `/view`. It prints the saved file paths as JSON.

Batch: loop over seeds or prompts and call the script once per variation.

## 4. API reference (server.py)

| Method & path | Use |
|---|---|
| `POST /prompt` `{"prompt": {...}, "client_id": "..."}` | Queue → `{"prompt_id", "number", "node_errors"}`; 400 with `node_errors` if invalid |
| `GET /history/{prompt_id}` | Status + `outputs[node_id].images[] = {filename, subfolder, type}` |
| `GET /view?filename=&subfolder=&type=output` | Download a file |
| `POST /upload/image` (multipart `image`, optional `overwrite=true`) | Put an input image into `input/` for `LoadImage` |
| `GET /queue` · `POST /interrupt` · `POST /free` | Queue state · stop current job · unload models |
| `GET /object_info[/{node_class}]` | Node definitions, valid input values (e.g. model names) |
| `GET /ws?clientId=...` | Live progress (`progress`, `executing`, `executed` messages) |

Upload example:

```bash
curl -F "image=@input.png" -F "overwrite=true" http://127.0.0.1:8188/upload/image
# then set the LoadImage node: --set 10.image=input.png
```

## 5. Troubleshooting

- `400` with `node_errors` → a required input is missing or a value (e.g. `ckpt_name`) is not in the list from `/object_info/<Class>`.
- `Value not in list` for a model → the file is not in the right `models/` subfolder; restart or refresh after adding.
- Out of memory → `--lowvram`, smaller resolution / batch size, or `POST /free`.
- Missing custom node class → install that custom node into `custom_nodes/` and restart.

## Rules

- Never expose the server with `--listen` on an untrusted network without the user's OK.
- Confirm the model files exist before queueing large batches.
- Tell the user where the outputs were saved.

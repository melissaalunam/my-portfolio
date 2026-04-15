# Krita MCP Server

## Architecture
Two-part system:
1. **Krita plugin** — runs inside Krita, TCP socket on `localhost:9999`
   `krita_plugin/krita_mcp_server/__init__.py`
2. **MCP server** — FastMCP process Claude talks to
   `server.py`

## Deploy after any plugin change
```bash
cp -r mcp/krita_plugin/krita_mcp_server ~/Library/Application\ Support/krita/pykrita/
```
Then **restart Krita**. No restart needed for `server.py` changes.

## Registration
Added via `claude mcp add` — stored in `~/.claude.json`. venv at `mcp/venv/`.

## Commands (socket protocol)
Request: `{"command": "...", "params": {...}}\n`
Response: `{"status": "ok"/"error"/"partial", "result": {...}}\n`

| Command | Key params |
|---|---|
| `ping` | — |
| `debug_info` | — → layer tree, filter list, node/doc methods |
| `open_document` | `path` |
| `create_canvas` | `width height dpi color_space bit_depth background name` |
| `setup_layer_structure` | `document_id structure` (omit for default illustration stack) |
| `apply_adjustments` | `document_id layer_name adjustments` |
| `batch_export` | `sources exports output_dir name_template` |

## apply_adjustments — working filters & ranges
```
brightness_contrast  brightness -255..255  contrast -255..255
hue_saturation       hue -180..180  saturation -100..100  value -100..100
levels               input_black 0..255  input_white 0..255  gamma 0.1..10
sharpen              amount 0..1  radius 0..5  threshold 0..255
colorbalance         shadows/midtones/highlights _red/_green/_blue -100..100
```
Confirmed filter IDs: `hsvadjustment levels sharpen unsharp colorbalance asc-cdl autocontrast blur`
Apply method: `filter.apply(node, 0, 0, w, h)` — NOT `node.applyFilter()` (doesn't exist)

## Known gotchas
- `brightness_contrast` filter doesn't exist — simulated via `levels` (gamma + input range)
- `setColorLabelIndex` doesn't exist on Node — guarded with `hasattr`
- Adjustments on an empty layer do nothing — always target the layer with actual pixels
- Opening a photo creates a layer named `Background` — apply adjustments there
- `node.uniqueId()` returns a PyQt5 QUuid object, not a plain string
- Plugin changes require full Krita quit+reopen, not just document close
- `resize_to` via InfoObject is silently ignored by Krita — resize is done by cloning the doc, calling `doc.scaleImage()`, exporting the clone, then closing it
- `doc.waitForDone()` must be called after `filter.apply()` and before `exportImage()` — without it the export fires before pixel changes are flushed and the output looks like the original
- Export overwrites are blocked by default — delete the old file or change `name_template` before re-exporting

## Photo editing workflow (Instagram)
```
open_document path=/path/to/photo.heic
apply_adjustments layer_name=Background adjustments={brightness_contrast, hue_saturation, levels}
# manual retouch in Krita (healing/clone — not automatable)
batch_export sources=["active"] exports=[{format:jpeg, quality:95, resize_to:{width:1080,height:1350}}] output_dir=~/Desktop
```
Reference images added to this folder for visual comparison:
- `image before.jpg` — original HEIC converted, no adjustments
- `image after.jpg` — after brightness+15, contrast+20, saturation+15, value+5, levels tightened, resized to 1080×1350 for Instagram
Confirmed adjustments for that session: brightness+15, contrast+20, saturation+15, value+5, levels input_black=10 input_white=245 gamma=1.1

## Quick smoke test
```bash
nc -zv localhost 9999   # must succeed before anything else
```
Full 6-step smoke test in `plan.md`.

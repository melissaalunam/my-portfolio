# Plan: Local MCP Server — Claude ↔ Krita (Digital Art & Illustration)

---

## Connection and Utility

This server bridges Claude (running in Claude Code) and **Krita**, an open-source digital painting application. Krita has a built-in Python scripting API (`pykrita`) that can control the application programmatically: create documents, build layer stacks, configure brushes, and export files.

**Why it fits this workflow:**
The illustration pipeline has a consistent, repeatable setup phase — new canvas, correct DPI, named layer stack — that happens before any creative work begins. It is mechanical, error-prone when done manually, and consumes focus that should go to drawing. Delegating this to Claude means the artist opens Krita and finds a ready workspace. Batch export at the end is the same kind of task: repetitive, configuration-heavy, and a poor use of creative attention.

The server enables Claude and subagents to own the start and end of every session — canvas setup, layer scaffolding, and export — while the artist handles everything in between.

---

## Top 3 Tools

### 1. `create_canvas`
**What it does:** Creates a new Krita document with specified dimensions, resolution, color space, and background fill. Replaces the manual new-document dialog and ensures consistent settings across all projects.

**Inputs:**
| Parameter | Type | Description |
|---|---|---|
| `width` | int | Canvas width in pixels |
| `height` | int | Canvas height in pixels |
| `dpi` | int | Resolution (e.g. 72 for web, 300 for print) |
| `color_space` | string | `"sRGB"`, `"CMYK"`, or `"Linear Light"` |
| `bit_depth` | string | `"8"`, `"16"`, or `"32"` (default `"8"`) |
| `background` | string | `"white"`, `"black"`, or `"transparent"` (default `"white"`) |
| `name` | string | Document name / filename stub |

**Returns:** Confirmation that the document was created, its Krita-assigned internal ID, and the canvas dimensions as confirmed by Krita.

---

### 2. `setup_layer_structure`
**What it does:** Builds a named, ordered layer stack inside the active document. Creates groups and layers with correct blend modes, opacity, and lock state — the full illustration scaffold in one call. Eliminates the repetitive manual work of creating and naming the same layers for every piece.

**Inputs:**
| Parameter | Type | Description |
|---|---|---|
| `document_id` | string | ID returned by `create_canvas`, or `"active"` to use the open document |
| `structure` | array of objects | Ordered list (top to bottom) of layer definitions — see below |

Each layer definition object:
| Field | Type | Description |
|---|---|---|
| `name` | string | Layer name (e.g. `"Lineart"`, `"Flat Colors"`) |
| `type` | string | `"paint"`, `"group"`, or `"fill"` |
| `blend_mode` | string | Krita blend mode key (e.g. `"normal"`, `"multiply"`, `"screen"`) |
| `opacity` | int | 0–100, default 100 |
| `locked` | bool | Whether to lock the layer (useful for sketch/reference layers) |
| `color_label` | string | Optional color label: `"red"`, `"orange"`, `"yellow"`, `"green"`, `"blue"`, `"purple"`, `"grey"` |
| `children` | array | Nested layer definitions if `type` is `"group"` |

**Returns:** The names and Krita node IDs of all created layers, in stack order.

**Default illustration stack (used when `structure` is omitted):**
```
[ Group: Line & Sketch ]
  — Lineart        (Multiply, locked after inking)
  — Sketch         (Multiply, 40% opacity, locked)
[ Group: Color ]
  — Shading        (Multiply)
  — Highlights     (Screen)
  — Flat Colors    (Normal)
[ Background ]     (Normal, locked)
```

---

### 3. `batch_export`
**What it does:** Exports one or more open Krita documents (or `.kra` files on disk) to multiple output formats in a single call. Handles format-specific settings (JPEG quality, PNG metadata strip, PSD compatibility) consistently.

**Inputs:**
| Parameter | Type | Description |
|---|---|---|
| `sources` | array of strings | Paths to `.kra` files, or `["active"]` to use the currently open document |
| `exports` | array of objects | One entry per desired output format |
| `output_dir` | string | Directory for all exported files; defaults to same folder as each source |
| `name_template` | string | Output filename pattern; supports `{name}`, `{date}`, `{format}` tokens |

Each export object:
| Field | Type | Description |
|---|---|---|
| `format` | string | `"png"`, `"jpeg"`, `"psd"`, `"webp"`, `"tiff"` |
| `quality` | int | 1–100 (JPEG/WebP only; default 90) |
| `flatten` | bool | Merge all layers before export (default `true` for JPEG/PNG, `false` for PSD) |
| `strip_metadata` | bool | Remove EXIF/XMP for web output (default `false`) |
| `resize_to` | object | Optional `{ "width": int, "height": int }` |

**Returns:** A list of exported file paths, their sizes in KB, and a per-file status (`success` / `error` with reason).

---

## Dependencies

| Dependency | Role |
|---|---|
| **Krita ≥ 5.0** | The application being controlled; must be installed with Python scripting enabled |
| **Python 3.10+** | Required by FastMCP; also the version Krita 5.x bundles internally |
| **FastMCP** (`fastmcp`) | Framework for building the MCP server |
| **Krita socket plugin** (custom, part of this project) | A small plugin installed inside Krita that starts a local TCP socket server |
| `socket` / `asyncio` (stdlib) | Communication between the MCP server process and the Krita plugin |

**Why a plugin is required:**
Krita's Python API (`pykrita`) can only be called from *inside* a running Krita instance. The architecture is two-part:
1. A Krita plugin (installed in `~/Library/Application Support/krita/pykrita/`) that listens on a local socket
2. A FastMCP server (standalone process) that translates MCP tool calls into JSON messages sent to that socket

---

## Configuration

| Item | Details |
|---|---|
| **No API keys** | Krita is local; no cloud services are involved |
| `KRITA_MCP_PORT` | Socket port; defaults to `9999` |
| `KRITA_MCP_HOST` | Always `127.0.0.1` |
| **Plugin install path** | macOS: `~/Library/Application Support/krita/pykrita/` |
| **Plugin activation** | Enable once in `Settings → Configure Krita → Python Plugin Manager`, then restart Krita |
| **MCP server registration** | Add to `.claude/settings.json` under `mcpServers` |
| **Virtual environment** | `mcp/venv/` — separate from Krita's bundled Python |

**One-time setup sequence:**
1. Install Krita 5.x and enable Python scripting in settings
2. Copy `krita_plugin/krita_mcp_server/` and `krita_plugin/krita_mcp_server.desktop` into `~/Library/Application Support/krita/pykrita/`
3. Enable the plugin in Krita's Plugin Manager and restart Krita
4. `cd mcp && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
5. Add the MCP server to `.claude/settings.json` (see Configuration section)
6. Restart Claude Code and verify with `nc -zv localhost 9999`

---

## Security Considerations

**Data that could be exposed:**
- File paths and layer names travel through the local socket and appear in Claude's context
- No image pixel data is transmitted — only commands and metadata

**Actions that could cause harm:**
| Risk | Mitigation |
|---|---|
| `batch_export` overwrites existing files | Require explicit `overwrite: true`; append `{date}` to default filenames |
| Bad `structure` corrupts unsaved document | v1 is append-only — no delete operations |
| Socket accepts connections from other local processes | Bind to `127.0.0.1` only |

**Scope limits:** Tools operate only on explicitly named files or the active document. No directory scans. No deletions in v1.

---

## Compatibility

| Issue | Details |
|---|---|
| **Two Python interpreters** | Krita's bundled Python and the MCP venv Python are independent — do not share packages |
| **FastMCP version** | Pin `fastmcp >= 0.4` |
| **Apple Silicon** | Krita may run under Rosetta; MCP venv uses native arm64 Python — independent processes, no crash risk |
| **Krita 4.x** | Not supported — targets Krita 5.x only |
| **Port conflict** | Use `KRITA_MCP_PORT` to remap if 9999 is in use |

---

## Risks and Constraints

- **Krita must be open** before any tool call — clear connection error returned, no hang
- **Single active document** — multi-document workflows need explicit document IDs
- **No undo stack guarantee** — always work on copies, not originals
- **No brush strokes** — drawing programmatically is out of scope in v1
- **Slow batch export** — large files can take several seconds; prefer one file per call for large batches
- **PSD round-trip** — filter and vector layers are rasterized on PSD export

---

## Smoke Test

Run these steps in order after initial setup. Each step depends on the previous succeeding.

**Preconditions:** Krita open, plugin enabled, MCP server registered, Claude Code restarted.

### Step 1 — Socket connection
`nc -zv localhost 9999` → connection accepted immediately.

### Step 2 — `create_canvas`
`width: 800, height: 600, dpi: 72, color_space: "sRGB", bit_depth: "8", background: "white", name: "smoke_test"`
→ Document `smoke_test` appears in Krita at 800×600. Return includes non-empty `document_id`.

### Step 3 — `setup_layer_structure` (default)
Call with `document_id` from Step 2, no `structure`.
→ Layers panel shows full default stack. `Sketch` at 40% opacity. `Background` locked. Return lists 7 nodes with IDs.

### Step 4 — `setup_layer_structure` (custom)
`[{ "name": "Custom Top", "blend_mode": "screen", "opacity": 75 }, { "name": "Custom Bottom", "locked": true }]`
→ Two layers added. Blend mode and opacity confirmed in Krita UI.

### Step 5 — `batch_export`
`sources: ["active"], exports: [{ "format": "png" }, { "format": "jpeg", "quality": 90 }], output_dir: "/tmp/smoke_test_exports"`
→ Two files in `/tmp/smoke_test_exports/`. Both open in Preview. Sizes > 0 KB. Status `"success"`.

### Step 6 — Error handling
Quit Krita. Call `create_canvas` with any args.
→ Structured error returned within 3 seconds. No hang. No unhandled traceback.

**Pass criteria:** All 6 steps succeed. If any fails, diagnose that layer before continuing.

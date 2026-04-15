import json
import os
import socket
from typing import Optional

from fastmcp import FastMCP

HOST = os.environ.get("KRITA_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("KRITA_MCP_PORT", "9999"))

mcp = FastMCP("Krita MCP Server")


def _send(command: str, params: dict) -> dict:
    payload = json.dumps({"command": command, "params": params}).encode() + b"\n"
    try:
        with socket.create_connection((HOST, PORT), timeout=30) as sock:
            sock.sendall(payload)
            buf = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                if b"\n" in buf:
                    break
    except ConnectionRefusedError:
        raise RuntimeError(
            "Could not connect to Krita. Make sure Krita is open and the "
            "krita_mcp_server plugin is enabled in Settings → Configure Krita → "
            "Python Plugin Manager."
        )
    except TimeoutError:
        raise RuntimeError(
            f"Connection to Krita timed out. Check that port {PORT} is not blocked "
            "and the plugin is loaded."
        )

    line = buf.split(b"\n")[0]
    result = json.loads(line.decode())

    if result.get("status") == "error":
        raise RuntimeError(result.get("message", "Unknown error from Krita plugin"))

    return result.get("result", {})


@mcp.tool()
def open_document(path: str) -> dict:
    """
    Open an existing image or .kra file in Krita.

    path: absolute path to the file (supports .kra, .png, .jpg, .heic, .psd, .tiff, etc.)

    Returns the document name, dimensions, and DPI once opened.
    """
    return _send("open_document", {"path": path})


@mcp.tool()
def ping() -> dict:
    """Check that the Krita plugin is running and the socket connection works."""
    return _send("ping", {})


@mcp.tool()
def apply_adjustments(
    adjustments: dict,
    document_id: str = "active",
    layer_name: Optional[str] = None,
) -> dict:
    """
    Apply non-destructive colour and tone adjustments to a layer.

    adjustments: dict with any combination of the following keys:

      brightness_contrast:
        brightness  int  -255 to 255  (0 = no change)
        contrast    int  -255 to 255  (0 = no change)

      hue_saturation:
        hue         int  -180 to 180  (0 = no change)
        saturation  int  -100 to 100  (0 = no change)
        lightness   int  -100 to 100  (0 = no change)

      levels:
        input_black   int    0–255    (default 0)
        input_white   int    0–255    (default 255)
        gamma         float  0.1–10   (default 1.0)
        output_black  int    0–255    (default 0)
        output_white  int    0–255    (default 255)

      sharpen:
        amount     float  0.0–1.0  (default 0.5)
        radius     float  0.0–5.0  (default 1.0)
        threshold  int    0–255    (default 0)

    document_id: document name or "active".
    layer_name: layer to apply to. Defaults to the active layer.
    """
    params: dict = {"adjustments": adjustments, "document_id": document_id}
    if layer_name is not None:
        params["layer_name"] = layer_name
    return _send("apply_adjustments", params)


@mcp.tool()
def create_canvas(
    width: int,
    height: int,
    dpi: int = 300,
    color_space: str = "sRGB",
    bit_depth: str = "8",
    background: str = "white",
    name: str = "untitled",
) -> dict:
    """
    Create a new Krita document.

    color_space: "sRGB", "CMYK", or "Linear Light"
    bit_depth: "8", "16", or "32"
    background: "white", "black", or "transparent"
    """
    return _send("create_canvas", {
        "width": width,
        "height": height,
        "dpi": dpi,
        "color_space": color_space,
        "bit_depth": bit_depth,
        "background": background,
        "name": name,
    })


@mcp.tool()
def setup_layer_structure(
    document_id: str = "active",
    structure: Optional[list] = None,
) -> dict:
    """
    Build a named layer stack in a Krita document.

    document_id: name returned by create_canvas, or "active" for the current document.

    structure: ordered list (top to bottom) of layer definition objects. Each object:
      - name (str): layer name
      - type (str): "paint", "group", or "fill"
      - blend_mode (str): e.g. "normal", "multiply", "screen"
      - opacity (int): 0-100, default 100
      - locked (bool): default false
      - color_label (str): "red", "orange", "yellow", "green", "blue", "purple", "grey"
      - children (list): nested layers, only valid when type is "group"

    If structure is omitted, the default illustration stack is used:
      Line & Sketch group (Lineart + Sketch), Color group (Shading + Highlights + Flat Colors), Background.
    """
    params: dict = {"document_id": document_id}
    if structure is not None:
        params["structure"] = structure
    return _send("setup_layer_structure", params)


@mcp.tool()
def batch_export(
    sources: list,
    exports: list,
    output_dir: Optional[str] = None,
    name_template: str = "{name}_{format}_{date}",
) -> dict:
    """
    Export one or more Krita documents to multiple formats.

    sources: list of file paths to .kra files, or ["active"] for the open document.

    exports: list of export spec objects. Each object:
      - format (str): "png", "jpeg", "psd", "webp", or "tiff"
      - quality (int): 1-100, JPEG/WebP only, default 90
      - flatten (bool): merge layers before export, default true for JPEG/PNG
      - strip_metadata (bool): remove EXIF/XMP, default false
      - resize_to (object): optional {"width": int, "height": int}

    output_dir: destination folder. Defaults to each source file's own directory.

    name_template: filename pattern supporting {name}, {format}, {date} tokens.
    Existing files are never overwritten — pass a unique name_template or include {date}.
    """
    params: dict = {
        "sources": sources,
        "exports": exports,
        "name_template": name_template,
    }
    if output_dir is not None:
        params["output_dir"] = output_dir
    return _send("batch_export", params)


if __name__ == "__main__":
    mcp.run()

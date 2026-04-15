import json
import os
import queue
import socket
import threading
from datetime import datetime

from krita import Extension, Krita, InfoObject
from PyQt5.QtCore import QTimer

HOST = os.environ.get("KRITA_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("KRITA_MCP_PORT", "9999"))

_command_queue = queue.Queue()
_server_started = False


class KritaMCPExtension(Extension):

    def __init__(self, parent):
        super().__init__(parent)
        self._timer = None

    def setup(self):
        pass

    def createActions(self, window):
        global _server_started
        if _server_started:
            return
        _server_started = True

        self._timer = QTimer()
        self._timer.timeout.connect(self._process_queue)
        self._timer.start(50)

        thread = threading.Thread(target=self._run_server, daemon=True)
        thread.start()

    def _run_server(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind((HOST, PORT))
                server.listen(5)
                while True:
                    conn, _ = server.accept()
                    threading.Thread(
                        target=self._handle_connection, args=(conn,), daemon=True
                    ).start()
        except Exception as e:
            print(f"[krita_mcp_server] Server error: {e}")

    def _handle_connection(self, conn):
        with conn:
            buf = b""
            while True:
                try:
                    chunk = conn.recv(4096)
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        command = json.loads(line.decode())
                    except json.JSONDecodeError as e:
                        self._send(conn, {"status": "error", "message": f"Invalid JSON: {e}"})
                        continue

                    result_q = queue.Queue()
                    _command_queue.put((command, result_q))
                    try:
                        result = result_q.get(timeout=30)
                    except queue.Empty:
                        result = {"status": "error", "message": "Command timed out after 30s"}
                    self._send(conn, result)

    def _send(self, conn, payload):
        try:
            conn.sendall(json.dumps(payload).encode() + b"\n")
        except OSError:
            pass

    def _process_queue(self):
        try:
            while True:
                command, result_q = _command_queue.get_nowait()
                try:
                    result = self._dispatch(command)
                except Exception as e:
                    result = {"status": "error", "message": str(e)}
                result_q.put(result)
        except queue.Empty:
            pass

    def _dispatch(self, command):
        name = command.get("command")
        params = command.get("params", {})
        handlers = {
            "ping": self._handle_ping,
            "debug_info": self._handle_debug_info,
            "open_document": self._handle_open_document,
            "apply_adjustments": self._handle_apply_adjustments,
            "create_canvas": self._handle_create_canvas,
            "setup_layer_structure": self._handle_setup_layer_structure,
            "batch_export": self._handle_batch_export,
        }
        handler = handlers.get(name)
        if not handler:
            return {"status": "error", "message": f"Unknown command: {name!r}"}
        return handler(params)

    def _handle_ping(self, params):
        return {"status": "ok", "result": {"message": "pong"}}

    def _handle_debug_info(self, params):
        doc = Krita.instance().activeDocument()
        node = doc.activeNode() if doc else None

        def node_tree(n, depth=0):
            rows = [{"depth": depth, "name": n.name(), "type": n.type(),
                     "locked": n.locked(), "visible": n.visible()}]
            for child in n.childNodes():
                rows.extend(node_tree(child, depth + 1))
            return rows

        layers = []
        if doc:
            for n in doc.rootNode().childNodes():
                layers.extend(node_tree(n))

        return {
            "status": "ok",
            "result": {
                "layers": layers,
                "filters": sorted(Krita.instance().filters()),
                "node_methods": [m for m in dir(node) if not m.startswith("_")] if node else [],
                "doc_methods":  [m for m in dir(doc)  if not m.startswith("_")] if doc else [],
            }
        }

    def _handle_open_document(self, params):
        path = params.get("path", "")
        if not path:
            return {"status": "error", "message": "path is required"}
        if not os.path.exists(path):
            return {"status": "error", "message": f"File not found: {path}"}

        doc = Krita.instance().openDocument(path)
        if not doc:
            return {"status": "error", "message": f"Krita could not open: {path}"}

        Krita.instance().activeWindow().addView(doc)

        return {
            "status": "ok",
            "result": {
                "document_id": doc.name(),
                "name": doc.name(),
                "width": doc.width(),
                "height": doc.height(),
                "dpi": doc.resolution(),
                "path": path,
            },
        }

    def _handle_apply_adjustments(self, params):
        doc_id = params.get("document_id", "active")
        layer_name = params.get("layer_name")
        adjustments = params.get("adjustments", {})

        doc = self._resolve_document(doc_id)
        if not doc:
            return {"status": "error", "message": "No document found"}

        if layer_name:
            node = self._find_node(doc.rootNode(), layer_name)
            if not node:
                return {"status": "error", "message": f"Layer not found: {layer_name!r}"}
        else:
            node = doc.activeNode()
            if not node:
                return {"status": "error", "message": "No active layer"}

        w, h = doc.width(), doc.height()
        applied = []
        errors = []

        def apply_filter(filter_id, properties):
            f = Krita.instance().filter(filter_id)
            if f is None:
                raise RuntimeError(f"Filter {filter_id!r} not found in this Krita build")
            cfg = f.configuration()
            for k, v in properties.items():
                cfg.setProperty(k, v)
            f.setConfiguration(cfg)
            f.apply(node, 0, 0, w, h)

        # levels: maps brightness (+gamma) and contrast (input range) as well as raw levels
        # brightness_contrast is simulated via levels: gamma for brightness, input range for contrast
        if "brightness_contrast" in adjustments:
            try:
                a = adjustments["brightness_contrast"]
                brightness = int(a.get("brightness", 0))   # -255..255
                contrast   = int(a.get("contrast", 0))     # -255..255
                # Map brightness to gamma (positive = brighter)
                gamma = round(1.0 + brightness / 255.0, 3)
                gamma = max(0.1, min(10.0, gamma))
                # Map contrast to input range narrowing
                shrink = max(0, min(127, abs(contrast) // 2))
                in_black = shrink if contrast > 0 else 0
                in_white = (255 - shrink) if contrast > 0 else 255
                apply_filter("levels", {
                    "inBlack": in_black,
                    "inWhite": in_white,
                    "inGamma": gamma,
                    "outBlack": 0,
                    "outWhite": 255,
                })
                applied.append("brightness_contrast")
            except Exception as e:
                errors.append(f"brightness_contrast: {e}")

        # hsvadjustment: hue (-180..180), saturation (-100..100), value (-100..100)
        if "hue_saturation" in adjustments:
            try:
                a = adjustments["hue_saturation"]
                apply_filter("hsvadjustment", {
                    "hue":        int(a.get("hue", 0)),
                    "saturation": int(a.get("saturation", 0)),
                    "value":      int(a.get("lightness", a.get("value", 0))),
                    "type":       "HSV",
                })
                applied.append("hue_saturation")
            except Exception as e:
                errors.append(f"hue_saturation: {e}")

        # levels (raw): inBlack, inWhite, inGamma, outBlack, outWhite
        if "levels" in adjustments:
            try:
                a = adjustments["levels"]
                apply_filter("levels", {
                    "inBlack":  int(a.get("input_black", 0)),
                    "inWhite":  int(a.get("input_white", 255)),
                    "inGamma":  float(a.get("gamma", 1.0)),
                    "outBlack": int(a.get("output_black", 0)),
                    "outWhite": int(a.get("output_white", 255)),
                })
                applied.append("levels")
            except Exception as e:
                errors.append(f"levels: {e}")

        # sharpen: amount (0.0..1.0), radius (0.0..5.0), threshold (0..255)
        if "sharpen" in adjustments:
            try:
                a = adjustments["sharpen"]
                apply_filter("unsharp", {
                    "amount":    float(a.get("amount", 0.5)),
                    "radius":    float(a.get("radius", 1.0)),
                    "threshold": int(a.get("threshold", 0)),
                })
                applied.append("sharpen")
            except Exception as e:
                errors.append(f"sharpen: {e}")

        # colorbalance: shadows/midtones/highlights rgb shifts (-100..100 each)
        if "colorbalance" in adjustments:
            try:
                a = adjustments["colorbalance"]
                apply_filter("colorbalance", {
                    "cyan_red_shadows":         int(a.get("shadows_red",   0)),
                    "magenta_green_shadows":     int(a.get("shadows_green", 0)),
                    "yellow_blue_shadows":       int(a.get("shadows_blue",  0)),
                    "cyan_red_midtones":         int(a.get("midtones_red",   0)),
                    "magenta_green_midtones":    int(a.get("midtones_green", 0)),
                    "yellow_blue_midtones":      int(a.get("midtones_blue",  0)),
                    "cyan_red_highlights":       int(a.get("highlights_red",   0)),
                    "magenta_green_highlights":  int(a.get("highlights_green", 0)),
                    "yellow_blue_highlights":    int(a.get("highlights_blue",  0)),
                })
                applied.append("colorbalance")
            except Exception as e:
                errors.append(f"colorbalance: {e}")

        doc.waitForDone()
        doc.refreshProjection()

        return {
            "status": "ok" if not errors else "partial",
            "result": {
                "layer": node.name(),
                "applied": applied,
                "errors": errors,
            },
        }

    def _find_node(self, root, name):
        for node in root.childNodes():
            if node.name() == name:
                return node
            found = self._find_node(node, name)
            if found:
                return found
        return None

    def _handle_create_canvas(self, params):
        width = int(params.get("width", 1920))
        height = int(params.get("height", 1080))
        dpi = float(params.get("dpi", 300))
        color_space = params.get("color_space", "sRGB")
        bit_depth = str(params.get("bit_depth", "8"))
        background = params.get("background", "white")
        name = params.get("name", "untitled")

        color_model_map = {
            "sRGB": ("RGBA", "sRGB-elle-V2-srgbtrc.icc"),
            "CMYK": ("CMYK", "ISO Coated v2 300% (ECI)"),
            "Linear Light": ("RGBA", "sRGB-elle-V2-g10.icc"),
        }
        depth_map = {"8": "U8", "16": "U16", "32": "F32"}

        color_model, color_profile = color_model_map.get(
            color_space, ("RGBA", "sRGB-elle-V2-srgbtrc.icc")
        )
        krita_depth = depth_map.get(bit_depth, "U8")

        doc = Krita.instance().createDocument(
            width, height, name, color_model, krita_depth, color_profile, dpi
        )

        if background == "transparent":
            nodes = doc.rootNode().childNodes()
            if nodes:
                nodes[0].setPixelData(
                    bytes(width * height * 4), 0, 0, width, height
                )

        Krita.instance().activeWindow().addView(doc)
        doc.refreshProjection()

        return {
            "status": "ok",
            "result": {
                "document_id": doc.name(),
                "width": doc.width(),
                "height": doc.height(),
                "dpi": doc.resolution(),
                "name": doc.name(),
            },
        }

    def _handle_setup_layer_structure(self, params):
        doc_id = params.get("document_id", "active")
        structure = params.get("structure")

        doc = self._resolve_document(doc_id)
        if not doc:
            return {"status": "error", "message": "No document found"}

        if structure is None:
            structure = self._default_structure()

        root = doc.rootNode()
        all_info = []

        insert_above = None
        for layer_def in reversed(structure):
            node, info = self._create_node(doc, layer_def, root, above=insert_above)
            insert_above = node
            all_info.extend(info)

        doc.refreshProjection()

        return {"status": "ok", "result": {"layers": all_info}}

    def _create_node(self, doc, layer_def, parent, above=None):
        type_map = {
            "paint": "paintlayer",
            "group": "grouplayer",
            "fill": "filllayer",
        }
        krita_type = type_map.get(layer_def.get("type", "paint"), "paintlayer")

        node = doc.createNode(layer_def["name"], krita_type)
        parent.addChildNode(node, above)

        node.setBlendingMode(layer_def.get("blend_mode", "normal"))
        node.setOpacity(int(layer_def.get("opacity", 100) * 255 / 100))
        node.setLocked(layer_def.get("locked", False))

        color_label_map = {
            "red": 1, "orange": 2, "yellow": 3, "green": 4,
            "blue": 5, "purple": 6, "grey": 7,
        }
        color_label = layer_def.get("color_label")
        if color_label and hasattr(node, "setColorLabelIndex"):
            node.setColorLabelIndex(color_label_map.get(color_label, 0))

        info = [{"name": node.name(), "id": str(node.uniqueId()), "type": krita_type}]

        child_above = None
        for child_def in reversed(layer_def.get("children", [])):
            child_node, child_info = self._create_node(doc, child_def, node, above=child_above)
            child_above = child_node
            info.extend(child_info)

        return node, info

    def _default_structure(self):
        return [
            {
                "name": "Line & Sketch",
                "type": "group",
                "blend_mode": "normal",
                "opacity": 100,
                "children": [
                    {
                        "name": "Lineart",
                        "type": "paint",
                        "blend_mode": "multiply",
                        "opacity": 100,
                    },
                    {
                        "name": "Sketch",
                        "type": "paint",
                        "blend_mode": "multiply",
                        "opacity": 40,
                        "locked": True,
                    },
                ],
            },
            {
                "name": "Color",
                "type": "group",
                "blend_mode": "normal",
                "opacity": 100,
                "children": [
                    {"name": "Shading", "type": "paint", "blend_mode": "multiply", "opacity": 100},
                    {"name": "Highlights", "type": "paint", "blend_mode": "screen", "opacity": 100},
                    {"name": "Flat Colors", "type": "paint", "blend_mode": "normal", "opacity": 100},
                ],
            },
            {
                "name": "Background",
                "type": "paint",
                "blend_mode": "normal",
                "opacity": 100,
                "locked": True,
            },
        ]

    def _handle_batch_export(self, params):
        sources = params.get("sources", ["active"])
        exports_spec = params.get("exports", [{"format": "png"}])
        output_dir = params.get("output_dir")
        name_template = params.get("name_template", "{name}_{format}_{date}")

        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = []

        for source in sources:
            if source == "active":
                doc = Krita.instance().activeDocument()
                source_label = "active"
            else:
                doc = Krita.instance().openDocument(source)
                source_label = source

            if not doc:
                results.append({
                    "source": source_label,
                    "status": "error",
                    "message": "Could not open document",
                })
                continue

            doc_filename = doc.fileName()
            if doc_filename:
                doc_name = os.path.splitext(os.path.basename(doc_filename))[0]
                default_dir = os.path.dirname(doc_filename)
            else:
                doc_name = doc.name() or "untitled"
                default_dir = os.path.expanduser("~/Desktop")

            dest_dir = output_dir or default_dir
            os.makedirs(dest_dir, exist_ok=True)

            for exp in exports_spec:
                fmt = exp.get("format", "png").lower()
                quality = int(exp.get("quality", 90))
                strip_metadata = exp.get("strip_metadata", False)
                resize_to = exp.get("resize_to")

                ext = "jpg" if fmt == "jpeg" else fmt
                filename = (
                    name_template.format(name=doc_name, format=fmt, date=date_str)
                    + f".{ext}"
                )
                output_path = os.path.join(dest_dir, filename)

                if os.path.exists(output_path):
                    results.append({
                        "source": source_label,
                        "path": output_path,
                        "format": fmt,
                        "status": "error",
                        "message": "File already exists. Pass overwrite:true or change name_template.",
                    })
                    continue

                # Flush all pending operations before export
                doc.waitForDone()
                doc.refreshProjection()

                # Resize: clone doc, scale the clone, export, close clone
                export_doc = doc
                cloned = False
                if resize_to:
                    target_w = int(resize_to.get("width", doc.width()))
                    target_h = int(resize_to.get("height", doc.height()))
                    if target_w != doc.width() or target_h != doc.height():
                        export_doc = doc.clone()
                        export_doc.scaleImage(target_w, target_h, 100, 100, "Bicubic")
                        export_doc.waitForDone()
                        cloned = True

                export_config = InfoObject()
                if fmt in ("jpeg", "webp"):
                    export_config.setProperty("quality", quality)
                if fmt == "png":
                    export_config.setProperty("compression", 6)
                if strip_metadata:
                    export_config.setProperty("saveMetaData", False)

                success = export_doc.exportImage(output_path, export_config)
                if cloned:
                    export_doc.close()

                file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0

                results.append({
                    "source": source_label,
                    "path": output_path,
                    "format": fmt,
                    "size_kb": round(file_size / 1024, 1),
                    "status": "success" if success else "error",
                    "message": "" if success else "exportImage returned False — check Krita scripting console",
                })

        return {"status": "ok", "result": {"exports": results}}

    def _resolve_document(self, doc_id):
        if doc_id == "active":
            return Krita.instance().activeDocument()
        for doc in Krita.instance().documents():
            if doc.name() == doc_id:
                return doc
        return None


Krita.instance().addExtension(KritaMCPExtension(Krita.instance()))

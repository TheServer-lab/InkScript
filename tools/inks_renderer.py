from PIL import Image, ImageDraw
import re
import sys

# ----------------------------
# Utilities
# ----------------------------

def parse_color(c):
    if c == "none":
        return None
    if isinstance(c, tuple):
        return c
    if not isinstance(c, str):
        raise ValueError(f"Invalid color: {c!r}")
    if c.startswith("#") and len(c) == 7:
        return tuple(int(c[i:i+2], 16) for i in (1, 3, 5))
    raise ValueError(f"Invalid color: {c}")

def num(v):
    return float(v) if "." in v else int(v)

def parse_attr_tokens(tokens):
    """Given a list of tokens like ['stroke=#fff','strokeWidth=3'], return dict."""
    out = {}
    for t in tokens:
        if "=" in t:
            k, v = t.split("=", 1)
            out[k] = v
    return out

# ----------------------------
# Renderer
# ----------------------------

class InksRenderer:
    def __init__(self):
        self.width = 0
        self.height = 0
        self.background = (0, 0, 0, 255)
        self.layers = []

    def render(self, infile, outfile):
        with open(infile, "r", encoding="utf-8") as f:
            lines = f.readlines()

        self._parse(lines)

        img = Image.new("RGBA", (self.width, self.height), self.background)
        draw = ImageDraw.Draw(img)

        for layer in self.layers:
            if not layer.get("visible", True):
                continue
            for cmd in layer["commands"]:
                cmd(draw)

        img.save(outfile)
        print(f"[OK] Rendered → {outfile}")

    # ----------------------------
    # Parsing (index-based, robust)
    # ----------------------------

    def _parse(self, lines):
        idx = 0
        n = len(lines)

        # header
        while idx < n and lines[idx].strip() == "":
            idx += 1
        if idx >= n:
            raise ValueError("Empty file")
        header = lines[idx].strip()
        idx += 1
        if not header.startswith("inkscript"):
            raise ValueError("Invalid header")

        while idx < n:
            raw = lines[idx]
            idx += 1
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("canvas"):
                _, w, h = line.split()
                self.width = int(w)
                self.height = int(h)

            elif line.startswith("background"):
                parts = line.split(None, 1)
                if len(parts) == 2:
                    c = parts[1].strip()
                    self.background = parse_color(c) + (255,)

            elif line.startswith("layer"):
                # pass the current index into layer parser which will return new idx
                idx = self._parse_layer(line, lines, idx)

            else:
                # unknown top-level line: ignore
                continue

    def _parse_layer(self, first_line, lines, idx):
        # parse attributes like id=1 name="paint" visible=true
        attrs = dict(re.findall(r'(\w+)=(\"[^\"]+\"|\S+)', first_line))
        layer = {
            "id": attrs.get("id"),
            "name": attrs.get("name", "").strip('"'),
            "visible": attrs.get("visible", "true") == "true",
            "commands": [],
            "style": {
                "stroke": (255, 255, 255),
                "strokeWidth": 2
            }
        }

        n = len(lines)
        while idx < n:
            raw = lines[idx]
            idx += 1
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line == "}":
                break
            if line.startswith("set"):
                # e.g. set stroke=#fff
                _, rest = line.split(None, 1)
                if "=" in rest:
                    k, v = rest.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if k in ("fill", "stroke"):
                        layer["style"][k] = parse_color(v)
                    elif k == "strokeWidth":
                        layer["style"][k] = int(v)
                continue
            if line.startswith("draw"):
                idx = self._parse_draw(line, lines, idx, layer)
                continue
            # other statements (erase/transform) are currently ignored in rendering
            # but we keep iterating until we hit the closing brace
            continue

        self.layers.append(layer)
        return idx

    # ----------------------------
    # Draw Parsing (returns updated idx)
    # ----------------------------

    def _parse_draw(self, line, lines, idx, layer):
        tokens = line.split()
        if len(tokens) < 2:
            return idx
        kind = tokens[1]

        # RECT
        if kind == "rect":
            # tokens like: draw rect x=10 y=10 w=100 h=50 fill=#fff stroke=#000 strokeWidth=2
            args = parse_attr_tokens(tokens[2:])
            x = num(args["x"])
            y = num(args["y"])
            w = num(args["w"])
            h = num(args["h"])
            fill = parse_color(args.get("fill", "none")) if "fill" in args else None
            stroke = parse_color(args.get("stroke", "none")) if "stroke" in args else None
            sw = int(args.get("strokeWidth", layer["style"]["strokeWidth"]))

            def cmd(draw):
                if fill:
                    draw.rectangle([x, y, x + w, y + h], fill=fill)
                if stroke:
                    draw.rectangle([x, y, x + w, y + h], outline=stroke, width=sw)

            layer["commands"].append(cmd)
            return idx

        # CIRCLE
        if kind == "circle":
            args = parse_attr_tokens(tokens[2:])
            cx = num(args["cx"])
            cy = num(args["cy"])
            r = num(args["r"])
            fill = parse_color(args.get("fill", "none")) if "fill" in args else None
            stroke = parse_color(args.get("stroke", "none")) if "stroke" in args else None
            sw = int(args.get("strokeWidth", layer["style"]["strokeWidth"]))

            box = [cx - r, cy - r, cx + r, cy + r]

            def cmd(draw):
                if fill:
                    draw.ellipse(box, fill=fill)
                if stroke:
                    draw.ellipse(box, outline=stroke, width=sw)

            layer["commands"].append(cmd)
            return idx

        # PATH (robust)
        if kind == "path":
            points = []
            n = len(lines)
            style_tokens = []
            # First, check if the opening line has any attrs (e.g. draw path id=stroke42 { )
            # We'll treat attrs on the opening line as path attributes (ignored for rendering)
            # Now read until we find the line that contains the closing brace.
            while idx < n:
                raw = lines[idx]
                idx += 1
                pline = raw.rstrip("\n")
                stripped = pline.strip()

                if not stripped or stripped.startswith("#"):
                    # skip blank or comment inside path block
                    continue

                # if stripped starts with "}" it might contain trailing style tokens
                if stripped.startswith("}"):
                    trailing = stripped[1:].strip()
                    if trailing:
                        # tokens may be like: stroke=#fff strokeWidth=3
                        style_tokens = trailing.split()
                    else:
                        # lookahead for a following non-empty non-comment line that looks like style tokens
                        # but do not consume unrelated lines (we will only consume it if it looks like style tokens)
                        look_idx = idx
                        while look_idx < n:
                            nxt = lines[look_idx].strip()
                            if not nxt or nxt.startswith("#"):
                                look_idx += 1
                                continue
                            # If the next line contains '=' and doesn't start with a keyword, treat as style line
                            if "=" in nxt and not nxt.split()[0] in ("draw", "set", "layer", "transform", "erase", "canvas", "background"):
                                style_tokens = nxt.split()
                                idx = look_idx + 1  # consume that style line
                            # otherwise do not consume it
                            break
                    break

                # Normal path commands: move, line, curve, close
                parts = stripped.split()
                cmdname = parts[0].lower()
                if cmdname in ("move", "line") and len(parts) >= 3:
                    try:
                        x, y = float(parts[1]), float(parts[2])
                        points.append((x, y))
                    except Exception:
                        continue
                elif cmdname == "curve" and len(parts) >= 7:
                    # We will approximate curve by sampling control points (basic support)
                    try:
                        # For now: treat as polyline through the last control point for deterministic rendering.
                        # A full bezier implementation can be added later.
                        x, y = float(parts[-2]), float(parts[-1])
                        points.append((x, y))
                    except Exception:
                        continue
                elif cmdname == "close":
                    # optionally connect to first point (we'll handle this in rendering if needed)
                    continue
                else:
                    # unknown/unsupported command inside path, skip
                    continue

            # parse style tokens (if any)
            style = parse_attr_tokens(style_tokens)
            stroke = parse_color(style.get("stroke", "#ffffff")) if "stroke" in style else layer["style"].get("stroke")
            sw = int(style.get("strokeWidth", layer["style"]["strokeWidth"])) if "strokeWidth" in style else layer["style"]["strokeWidth"]

            def cmd(draw):
                if len(points) > 1 and stroke:
                    draw.line(points, fill=stroke, width=sw)

            layer["commands"].append(cmd)
            return idx

        # TEXT (basic)
        if kind == "text":
            # expecting format: draw text "..." x=NUM y=NUM [opts...]
            m = re.match(r'draw text\s+"(.+?)"(.*)', line)
            if not m:
                return idx
            text = m.group(1)
            rest = m.group(2).strip()
            tokens = rest.split()
            args = parse_attr_tokens(tokens)
            x = int(float(args.get("x", 0)))
            y = int(float(args.get("y", 0)))
            color = parse_color(args.get("color", "#000000")) if "color" in args else (255, 255, 255)
            # very basic text rendering (Pillow default font)
            def cmd(draw):
                draw.text((x, y), text, fill=color)
            layer["commands"].append(cmd)
            return idx

        # Unknown draw kind: consume nothing more and return
        return idx

# ----------------------------
# CLI
# ----------------------------

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python inks_renderer.py input.inks output.png")
        sys.exit(1)

    InksRenderer().render(sys.argv[1], sys.argv[2])

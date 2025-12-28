#!/usr/bin/env python3
"""
InkPaint — expanded editor that saves .inks (InkScript).

Features:
- Brush + Eraser
- Layers (add/remove/visibility)
- Save / Open .inks (basic)
- Export PNG
- Undo / Redo (add stroke, erase)
- Color picker, size slider
"""

import tkinter as tk
from tkinter import filedialog, colorchooser, simpledialog, messagebox
from PIL import Image, ImageDraw
import re
import os
import math
import time

# ----------------------------
# Models
# ----------------------------

class Stroke:
    def __init__(self, stroke_id, color, width, points=None):
        self.id = stroke_id
        self.color = color
        self.width = width
        self.points = points or []
        self.erased = False  # non-destructive erase marker

class Layer:
    def __init__(self, layer_id, name="Layer", visible=True):
        self.id = layer_id
        self.name = name
        self.visible = visible
        self.strokes = []

# ----------------------------
# Undo/Redo Actions
# ----------------------------

class ActionAddStroke:
    def __init__(self, layer_id, stroke):
        self.layer_id = layer_id
        self.stroke = stroke

class ActionEraseStrokes:
    def __init__(self, layer_id, stroke_ids):
        self.layer_id = layer_id
        self.stroke_ids = stroke_ids

# ----------------------------
# InkPaint App
# ----------------------------

class InkPaint:
    def __init__(self, root):
        self.root = root
        self.root.title("InkPaint (.inks editor)")

        # canvas size
        self.width = 1000
        self.height = 700
        self.bg_color = "#0b0d12"

        # document model
        self.layers = []
        self.layer_counter = 1
        self.current_layer_index = 0  # index into self.layers

        # strokes & ids
        self.stroke_counter = 1

        # tools
        self.tool = "brush"  # brush | eraser
        self.color = "#ffffff"
        self.stroke_width = 3
        self.eraser_width = 20

        # history
        self.undo_stack = []
        self.redo_stack = []

        # UI setup
        self._build_ui()
        self.new_document()

    # ----------------------------
    # UI
    # ----------------------------

    def _build_ui(self):
        # Menu
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=False)
        filemenu.add_command(label="New", command=self.new_document)
        filemenu.add_command(label="Open .inks...", command=self.open_inks)
        filemenu.add_command(label="Save .inks...", command=self.save_inks)
        filemenu.add_command(label="Export PNG...", command=self.export_png)
        filemenu.add_separator()
        filemenu.add_command(label="Quit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        editmenu = tk.Menu(menubar, tearoff=False)
        editmenu.add_command(label="Undo", command=self.undo, accelerator="Ctrl+Z")
        editmenu.add_command(label="Redo", command=self.redo, accelerator="Ctrl+Y")
        menubar.add_cascade(label="Edit", menu=editmenu)

        self.root.config(menu=menubar)
        self.root.bind_all("<Control-z>", lambda e: self.undo())
        self.root.bind_all("<Control-y>", lambda e: self.redo())

        # Top toolbar
        toolbar = tk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        tk.Button(toolbar, text="Brush", command=lambda: self.set_tool("brush")).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Eraser", command=lambda: self.set_tool("eraser")).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Add Layer", command=self.add_layer).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Remove Layer", command=self.remove_layer).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Toggle Visible", command=self.toggle_layer_visibility).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Save .inks", command=self.save_inks).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Open .inks", command=self.open_inks).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Export PNG", command=self.export_png).pack(side=tk.LEFT)

        tk.Label(toolbar, text="   ").pack(side=tk.LEFT)

        tk.Button(toolbar, text="Color", command=self.pick_color).pack(side=tk.LEFT)
        tk.Label(toolbar, text="Size").pack(side=tk.LEFT)
        self.size_slider = tk.Scale(toolbar, from_=1, to=60, orient=tk.HORIZONTAL, command=self._size_changed)
        self.size_slider.set(self.stroke_width)
        self.size_slider.pack(side=tk.LEFT)

        tk.Label(toolbar, text=" ").pack(side=tk.LEFT)
        tk.Button(toolbar, text="Clear Layer", command=self.clear_current_layer).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Flatten & Export PNG", command=self.export_png).pack(side=tk.LEFT)

        # Main frame
        main = tk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True)

        # Canvas area
        canvas_frame = tk.Frame(main)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg=self.bg_color, width=self.width, height=self.height)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Layer panel
        panel = tk.Frame(main, width=220)
        panel.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(panel, text="Layers").pack(anchor="nw")
        self.layers_listbox = tk.Listbox(panel)
        self.layers_listbox.pack(fill=tk.Y, expand=True)
        self.layers_listbox.bind("<<ListboxSelect>>", self.on_layer_select)

        layer_btns = tk.Frame(panel)
        layer_btns.pack(fill=tk.X)
        tk.Button(layer_btns, text="Up", command=self.move_layer_up).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(layer_btns, text="Down", command=self.move_layer_down).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Status bar
        self.status = tk.Label(self.root, text="Ready", anchor="w")
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

        # Bind events
        self.canvas.bind("<ButtonPress-1>", self.on_pointer_down)
        self.canvas.bind("<B1-Motion>", self.on_pointer_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_pointer_up)
        self.canvas.bind("<Motion>", self.on_pointer_motion)

        # Keep map of canvas IDs for quick deletion
        self._canvas_item_map = {}  # stroke_id -> [canvas_item_ids]

    # ----------------------------
    # Document management
    # ----------------------------

    def new_document(self):
        self.layers.clear()
        self.layer_counter = 1
        self.stroke_counter = 1
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.add_layer(name="Layer 1")
        self.current_layer_index = 0
        self._refresh_layer_list()
        self._redraw_canvas()
        self.status_set("New document")

    def add_layer(self, name=None):
        name = name or f"Layer {self.layer_counter}"
        layer = Layer(layer_id=self.layer_counter, name=name, visible=True)
        self.layer_counter += 1
        self.layers.insert(0, layer)  # new layer at top
        self.current_layer_index = 0
        self._refresh_layer_list()
        self._redraw_canvas()
        self.status_set(f"Added layer '{name}'")

    def remove_layer(self):
        if not self.layers:
            return
        idx = self.current_layer_index
        if idx < 0 or idx >= len(self.layers):
            return
        layer = self.layers.pop(idx)
        self.current_layer_index = max(0, min(idx, len(self.layers)-1))
        self._refresh_layer_list()
        self._redraw_canvas()
        self.status_set(f"Removed layer '{layer.name}'")

    def move_layer_up(self):
        idx = self.current_layer_index
        if idx > 0:
            self.layers[idx-1], self.layers[idx] = self.layers[idx], self.layers[idx-1]
            self.current_layer_index -= 1
            self._refresh_layer_list()
            self._redraw_canvas()

    def move_layer_down(self):
        idx = self.current_layer_index
        if idx < len(self.layers)-1:
            self.layers[idx+1], self.layers[idx] = self.layers[idx], self.layers[idx+1]
            self.current_layer_index += 1
            self._refresh_layer_list()
            self._redraw_canvas()

    def toggle_layer_visibility(self):
        layer = self._current_layer()
        if not layer:
            return
        layer.visible = not layer.visible
        self._refresh_layer_list()
        self._redraw_canvas()

    def clear_current_layer(self):
        layer = self._current_layer()
        if not layer:
            return
        removed_ids = [s.id for s in layer.strokes if not s.erased]
        layer.strokes.clear()
        self._canvas_delete_strokes(removed_ids)
        self.undo_stack.append(ActionEraseStrokes(layer.id, removed_ids))  # treat as erase action
        self.redo_stack.clear()
        self._redraw_canvas()
        self.status_set("Cleared current layer")

    def on_layer_select(self, event=None):
        sel = self.layers_listbox.curselection()
        if sel:
            self.current_layer_index = sel[0]
        else:
            self.current_layer_index = 0
        self._redraw_canvas()

    def _refresh_layer_list(self):
        self.layers_listbox.delete(0, tk.END)
        for i, layer in enumerate(self.layers):
            vis = "👁" if layer.visible else "🚫"
            self.layers_listbox.insert(tk.END, f"{vis} {layer.name} (id={layer.id})")
        if self.layers:
            self.layers_listbox.select_set(self.current_layer_index)

    def _current_layer(self):
        if not self.layers:
            return None
        idx = self.current_layer_index
        if idx < 0 or idx >= len(self.layers):
            return self.layers[0]
        return self.layers[idx]

    # ----------------------------
    # Tools
    # ----------------------------

    def set_tool(self, tool):
        self.tool = tool
        self.status_set(f"Tool: {tool}")

    def pick_color(self):
        c = colorchooser.askcolor(initialcolor=self.color)[1]
        if c:
            self.color = c
            self.status_set(f"Color: {self.color}")

    def _size_changed(self, val):
        v = int(float(val))
        if self.tool == "brush":
            self.stroke_width = v
        else:
            self.eraser_width = v
        # keep slider always reflecting stroke_width for brush
        self.size_slider.set(v)

    # ----------------------------
    # Pointer events (draw)
    # ----------------------------

    def on_pointer_down(self, e):
        layer = self._current_layer()
        if not layer:
            return

        x, y = e.x, e.y
        if self.tool == "brush":
            sid = f"stroke_{self.stroke_counter}"
            self.stroke_counter += 1
            s = Stroke(sid, self.color, self.stroke_width)
            s.points.append((x, y))
            layer.strokes.append(s)
            # draw immediate
            self._canvas_draw_point_segment(s, len(s.points)-1)
            # record current stroke being drawn
            self._active_stroke = s
            self._canvas_item_map.setdefault(s.id, [])
        elif self.tool == "eraser":
            # collect eraser "path" points and later detect hit strokes
            sid = f"eraser_{int(time.time()*1000)}"
            s = Stroke(sid, None, self.eraser_width)
            s.points.append((x, y))
            self._active_eraser = s
            self._canvas_item_map.setdefault(s.id, [])

    def on_pointer_move(self, e):
        x, y = e.x, e.y
        if self.tool == "brush" and getattr(self, "_active_stroke", None):
            s = self._active_stroke
            last = s.points[-1]
            s.points.append((x, y))
            self._canvas_draw_line_segment(last, (x, y), s.color, s.width, tag=s.id)
        elif self.tool == "eraser" and getattr(self, "_active_eraser", None):
            s = self._active_eraser
            last = s.points[-1]
            s.points.append((x, y))
            self._canvas_draw_line_segment(last, (x, y), self.bg_color, s.width, tag=s.id)

    def on_pointer_up(self, e):
        if self.tool == "brush" and getattr(self, "_active_stroke", None):
            s = self._active_stroke
            self._active_stroke = None
            # record action
            self.undo_stack.append(ActionAddStroke(self._current_layer().id, s))
            self.redo_stack.clear()
            self.status_set(f"Stroke added: {s.id} pts={len(s.points)}")
        elif self.tool == "eraser" and getattr(self, "_active_eraser", None):
            eraser = self._active_eraser
            self._active_eraser = None
            # perform hit-test: mark strokes within eraser path as erased
            erased_ids = self._apply_eraser_path(eraser.points, eraser.width)
            if erased_ids:
                self.undo_stack.append(ActionEraseStrokes(self._current_layer().id, erased_ids))
                self.redo_stack.clear()
                self.status_set(f"Erased {len(erased_ids)} stroke(s)")
            else:
                self.status_set("Eraser: nothing hit")

    def on_pointer_motion(self, e):
        self.status_set(f"Pos: {e.x},{e.y} | Tool: {self.tool}")

    # ----------------------------
    # Canvas helpers
    # ----------------------------

    def _canvas_draw_line_segment(self, p1, p2, color, width, tag=None):
        # draw line on canvas and record item id mapping for the stroke
        item = self.canvas.create_line(p1[0], p1[1], p2[0], p2[1],
                                       fill=color, width=width, capstyle=tk.ROUND, smooth=True, tags=(tag or ""))
        if tag:
            self._canvas_item_map.setdefault(tag, []).append(item)

    def _canvas_draw_point_segment(self, stroke, idx):
        # when stroke has only 1 point, create a small oval to show dot
        if len(stroke.points) == 1:
            x, y = stroke.points[0]
            r = max(1, stroke.width/2)
            item = self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=stroke.color, outline=stroke.color, tags=(stroke.id,))
            self._canvas_item_map.setdefault(stroke.id, []).append(item)

    def _canvas_delete_strokes(self, stroke_ids):
        for sid in stroke_ids:
            items = self._canvas_item_map.pop(sid, [])
            for it in items:
                try:
                    self.canvas.delete(it)
                except Exception:
                    pass

    def _redraw_canvas(self):
        # clears and redraws from model. layers are drawn from bottom (last) to top (first)
        self.canvas.delete("all")
        self._canvas_item_map.clear()
        for layer in reversed(self.layers):  # bottom-first
            if not layer.visible:
                continue
            for stroke in layer.strokes:
                if stroke.erased:
                    continue
                # draw each stroke as line segments
                if not stroke.points:
                    continue
                if len(stroke.points) == 1:
                    self._canvas_draw_point_segment(stroke, 0)
                else:
                    prev = stroke.points[0]
                    for pt in stroke.points[1:]:
                        self._canvas_draw_line_segment(prev, pt, stroke.color, stroke.width, tag=stroke.id)
                        prev = pt

    # ----------------------------
    # Eraser logic (simple hit test)
    # ----------------------------

    def _apply_eraser_path(self, path_points, eraser_width):
        """Given an eraser path, mark any stroke with any point within
        eraser_width/2 of any eraser point as erased. Return list of erased ids."""
        if not path_points:
            return []

        layer = self._current_layer()
        if not layer:
            return []

        rad = eraser_width / 2.0
        erased_ids = []
        for stroke in list(layer.strokes):
            if stroke.erased:
                continue
            # quick bbox check
            xs = [p[0] for p in stroke.points]
            ys = [p[1] for p in stroke.points]
            if not xs or not ys:
                continue
            minx, maxx = min(xs), max(xs)
            miny, maxy = min(ys), max(ys)
            # expand bbox by rad
            if maxx < min(p[0] for p in path_points) - rad or minx > max(p[0] for p in path_points) + rad:
                # bbox outside x-range
                # not a reliable skip in all cases but good enough
                pass
            # precise check: any point distance
            hit = False
            for ep in path_points:
                for sp in stroke.points:
                    dx = ep[0] - sp[0]
                    dy = ep[1] - sp[1]
                    if dx*dx + dy*dy <= rad*rad:
                        hit = True
                        break
                if hit:
                    break
            if hit:
                stroke.erased = True
                self._canvas_delete_strokes([stroke.id])
                erased_ids.append(stroke.id)
        return erased_ids

    # ----------------------------
    # Undo / Redo
    # ----------------------------

    def undo(self):
        if not self.undo_stack:
            self.status_set("Nothing to undo")
            return
        act = self.undo_stack.pop()
        if isinstance(act, ActionAddStroke):
            # remove the stroke from layer
            layer = self._layer_by_id(act.layer_id)
            if layer:
                # find and mark erased (or remove entirely)
                for s in layer.strokes:
                    if s.id == act.stroke.id:
                        layer.strokes.remove(s)
                        self._canvas_delete_strokes([s.id])
                        # push to redo as adding it back
                        self.redo_stack.append(act)
                        break
        elif isinstance(act, ActionEraseStrokes):
            layer = self._layer_by_id(act.layer_id)
            if layer:
                # un-erase those strokes
                restored = []
                for sid in act.stroke_ids:
                    for s in layer.strokes:
                        if s.id == sid:
                            s.erased = False
                            restored.append(sid)
                            break
                # redraw restored strokes
                self._redraw_canvas()
                self.redo_stack.append(act)
        self._redraw_canvas()
        self.status_set("Undo")

    def redo(self):
        if not self.redo_stack:
            self.status_set("Nothing to redo")
            return
        act = self.redo_stack.pop()
        if isinstance(act, ActionAddStroke):
            # re-add stroke
            layer = self._layer_by_id(act.layer_id)
            if layer:
                layer.strokes.append(act.stroke)
                # draw it
                if len(act.stroke.points) == 1:
                    self._canvas_draw_point_segment(act.stroke, 0)
                else:
                    prev = act.stroke.points[0]
                    for pt in act.stroke.points[1:]:
                        self._canvas_draw_line_segment(prev, pt, act.stroke.color, act.stroke.width, tag=act.stroke.id)
                        prev = pt
                self.undo_stack.append(act)
        elif isinstance(act, ActionEraseStrokes):
            layer = self._layer_by_id(act.layer_id)
            if layer:
                erased_now = []
                for sid in act.stroke_ids:
                    for s in layer.strokes:
                        if s.id == sid and not s.erased:
                            s.erased = True
                            erased_now.append(sid)
                            break
                self._canvas_delete_strokes(erased_now)
                self.undo_stack.append(act)
        self._redraw_canvas()
        self.status_set("Redo")

    def _layer_by_id(self, lid):
        for l in self.layers:
            if l.id == lid:
                return l
        return None

    # ----------------------------
    # Save / Load .inks
    # ----------------------------

    def save_inks(self):
        path = filedialog.asksaveasfilename(defaultextension=".inks", filetypes=[("InkScript", "*.inks")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("inkscript 1.0\n\n")
                f.write(f"canvas {self.width} {self.height}\n")
                f.write(f"background {self.bg_color}\n\n")
                # write layers in order (top first)
                for layer in self.layers:
                    f.write(f'layer id={layer.id} name="{layer.name}" visible={"true" if layer.visible else "false"} {{\n')
                    # layer style (none for now)
                    # write strokes in creation order
                    for s in layer.strokes:
                        # write only strokes that existed — if erased, write erase ref
                        if not s.erased:
                            f.write(f"  draw path id={s.id} {{\n")
                            first = True
                            for x, y in s.points:
                                cmd = "move" if first else "line"
                                f.write(f"    {cmd} {float(x):.2f} {float(y):.2f}\n")
                                first = False
                            f.write("  } ")
                            # write style inline
                            if s.color:
                                f.write(f"stroke={s.color} ")
                            f.write(f"strokeWidth={int(s.width)}\n\n")
                        else:
                            # erased: record as non-destructive erase operation
                            f.write(f"  erase ref={s.id}\n")
                    f.write("}\n\n")
            self.status_set(f"Saved {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Save error", str(e))
            self.status_set("Save failed")

    def open_inks(self):
        path = filedialog.askopenfilename(filetypes=[("InkScript", "*.inks"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            self._load_from_lines(lines)
            self.status_set(f"Opened {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Open error", str(e))
            self.status_set("Open failed")

    def _load_from_lines(self, lines):
        # minimal parser for draw path / erase ref and basic header
        self.layers.clear()
        self.layer_counter = 1
        self.stroke_counter = 1
        current_layer = None
        layer_map = {}
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("canvas"):
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        self.width = int(parts[1]); self.height = int(parts[2])
                    except:
                        pass
            elif line.startswith("background"):
                parts = line.split(None, 1)
                if len(parts) == 2:
                    self.bg_color = parts[1].strip()
            elif line.startswith("layer"):
                # finish previous layer
                attrs = dict(re.findall(r'(\w+)=(\"[^\"]+\"|\S+)', line))
                lid = int(attrs.get("id", self.layer_counter))
                name = attrs.get("name", f"Layer {lid}").strip('"')
                vis = attrs.get("visible", "true") == "true"
                current_layer = Layer(layer_id=lid, name=name, visible=vis)
                layer_map[lid] = current_layer
                if lid >= self.layer_counter:
                    self.layer_counter = lid + 1
                self.layers.append(current_layer)
            elif line.startswith("}"):
                current_layer = None
            elif line.startswith("draw") and "path" in line and current_layer:
                # parse header like: draw path id=stroke_1 {
                m = re.match(r'draw\s+path\s+([^{}]+)\{', line)
                if m:
                    attrs = m.group(1).strip()
                    attrs_d = dict(re.findall(r'(\w+)=(\"[^\"]+\"|\S+)', attrs))
                    sid = attrs_d.get("id", f"stroke_{self.stroke_counter}")
                else:
                    sid = f"stroke_{self.stroke_counter}"
                # read subsequent move/line lines until closing brace
                pts = []
                # find index of current line in raw list and read following lines - but we don't have index here
                # so we will rely on a simple approach: accumulate until we find '}' in subsequent raw lines
                # Instead, parse by consuming from lines generator — to simplify, re-scan via join
                # We'll fallback to scanning the whole file for blocks. Simpler approach:
                pass
        # Fallback robust parser using a stateful scan
        idx = 0
        n = len(lines)
        current_layer = None
        while idx < n:
            raw = lines[idx]; idx += 1
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("canvas"):
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        self.width = int(parts[1]); self.height = int(parts[2])
                    except:
                        pass
            elif line.startswith("background"):
                parts = line.split(None, 1)
                if len(parts) == 2:
                    self.bg_color = parts[1].strip()
            elif line.startswith("layer"):
                attrs = dict(re.findall(r'(\w+)=(\"[^\"]+\"|\S+)', line))
                lid = int(attrs.get("id", self.layer_counter))
                name = attrs.get("name", f"Layer {lid}").strip('"')
                vis = attrs.get("visible", "true") == "true"
                current_layer = Layer(layer_id=lid, name=name, visible=vis)
                if lid >= self.layer_counter:
                    self.layer_counter = lid + 1
                self.layers.append(current_layer)
            elif line == "}":
                current_layer = None
            elif line.startswith("draw") and "path" in line and current_layer:
                # parse id if present
                m = re.search(r'id=([^\s{]+)', line)
                sid = m.group(1) if m else f"stroke_{self.stroke_counter}"
                if sid.startswith('"') and sid.endswith('"'):
                    sid = sid.strip('"')
                # read path block
                pts = []
                # consume following lines until '}' is found
                while idx < n:
                    raw2 = lines[idx]; idx += 1
                    s2 = raw2.strip()
                    if not s2 or s2.startswith("#"):
                        continue
                    if s2.startswith("}"):
                        # try to capture inline style tokens after '}'
                        # (ignored for now)
                        break
                    parts = s2.split()
                    if parts[0] in ("move", "line") and len(parts) >= 3:
                        try:
                            x = float(parts[1]); y = float(parts[2])
                            pts.append((x, y))
                        except:
                            pass
                    # ignore other commands
                # after block, maybe style line present on same line or next line; try to capture stroke= and strokeWidth
                # look ahead one non-empty non-comment line for style tokens
                style = {}
                look_idx = idx
                while look_idx < n:
                    nxt = lines[look_idx].strip()
                    if not nxt or nxt.startswith("#"):
                        look_idx += 1
                        continue
                    # if line has '=' tokens and doesn't begin a keyword, treat as style
                    if "=" in nxt and not re.match(r'^(draw|set|layer|transform|erase|canvas|background)\b', nxt):
                        for token in nxt.split():
                            if "=" in token:
                                k, v = token.split("=", 1)
                                style[k] = v
                        idx = look_idx + 1
                    break
                color = style.get("stroke") or "#000000"
                width = int(float(style.get("strokeWidth", "2")))
                st = Stroke(sid, color, width, pts)
                current_layer.strokes.append(st)
                # update counters
                if sid.startswith("stroke_"):
                    try:
                        nnum = int(sid.split("_", 1)[1])
                        if nnum >= self.stroke_counter:
                            self.stroke_counter = nnum + 1
                    except:
                        pass
            elif line.startswith("erase") and current_layer:
                # e.g. erase ref=stroke_3
                m = re.search(r'ref=([^\s]+)', line)
                if m:
                    rid = m.group(1)
                    # find stroke in current layer and mark erased
                    for s in current_layer.strokes:
                        if s.id == rid:
                            s.erased = True
                            break
            else:
                # ignore other lines
                continue

        # refresh UI
        self._refresh_layer_list()
        self._redraw_canvas()
        self.status_set("Loaded .inks")

    # ----------------------------
    # Export PNG (simple renderer)
    # ----------------------------

    def export_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image", "*.png")])
        if not path:
            return
        try:
            img = Image.new("RGBA", (self.width, self.height), self._hex_to_rgb_alpha(self.bg_color))
            draw = ImageDraw.Draw(img)
            # layers bottom-first (reverse of list since we store top-first)
            for layer in reversed(self.layers):
                if not layer.visible:
                    continue
                for stroke in layer.strokes:
                    if stroke.erased:
                        continue
                    pts = stroke.points
                    if not pts:
                        continue
                    # convert hex color to RGBA tuple
                    col = self._hex_to_rgb(stroke.color or "#000000")
                    if len(pts) == 1:
                        x, y = pts[0]
                        r = max(1, stroke.width/2)
                        draw.ellipse([x-r, y-r, x+r, y+r], fill=col, outline=col)
                    else:
                        # flatten into tuple sequence
                        flat = [coord for p in pts for coord in p]
                        draw.line(flat, fill=col, width=int(stroke.width), joint="curve")
            img.save(path)
            self.status_set(f"Exported PNG: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Export error", str(e))
            self.status_set("Export failed")

    # ----------------------------
    # Helpers
    # ----------------------------

    def _hex_to_rgb(self, h):
        if not h:
            return (0,0,0)
        h = h.lstrip("#")
        if len(h) == 6:
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        if len(h) == 3:
            return tuple(int(h[i]*2, 16) for i in range(3))
        return (0,0,0)

    def _hex_to_rgb_alpha(self, h):
        rgb = self._hex_to_rgb(h)
        return (rgb[0], rgb[1], rgb[2], 255)

    def status_set(self, txt):
        self.status.config(text=txt)

# ----------------------------
# Run
# ----------------------------

if __name__ == "__main__":
    root = tk.Tk()
    app = InkPaint(root)
    root.mainloop()

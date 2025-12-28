#!/usr/bin/env python3
"""
InkPaint — improved editor that saves .inks (InkScript).

New features:
- Brush + Eraser + Line + Rect + Ellipse + Fill + Select
- Move selection (drag to move selected strokes)
- Zoom (mouse wheel) and Pan (right-button drag or Space+drag)
- Keyboard shortcuts: B, E, L, R, O, S, F
- Ctrl+Click eyedropper (pick stroke color under cursor)
- Autosave & crash recovery (.inkautosave.inks)
- Undo/Redo supports add/erase/move
- Saves `fill=` for filled strokes

Dependencies:
- Pillow (for export)
- Tkinter (standard)
"""
import tkinter as tk
from tkinter import filedialog, colorchooser, messagebox
from PIL import Image, ImageDraw
import re
import os
import math
import time
import copy
import tempfile
import json

AUTOSAVE_FILENAME = os.path.join(tempfile.gettempdir(), "inkscript_autosave.inks")
AUTOSAVE_INTERVAL_MS = 60_000  # 60 seconds

# ----------------------------
# Models
# ----------------------------

class Stroke:
    def __init__(self, stroke_id, color="#000000", width=2, points=None, fill=None):
        self.id = stroke_id
        self.color = color
        self.width = width
        self.points = points or []
        self.erased = False  # non-destructive erase
        self.fill = fill  # optional fill color

    def copy_points(self):
        return [ (x,y) for (x,y) in self.points ]

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

class ActionMoveStrokes:
    def __init__(self, layer_id, stroke_snapshots):  # list of (stroke_id, old_pts, new_pts)
        self.layer_id = layer_id
        self.stroke_snapshots = stroke_snapshots

# ----------------------------
# InkPaint App
# ----------------------------

class InkPaint:
    def __init__(self, root):
        self.root = root
        self.root.title("InkPaint (.inks editor)")

        # canvas size (document coords)
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
        # brush | eraser | line | rect | ellipse | select | fill
        self.tool = "brush"
        self.color = "#ffffff"
        self.stroke_width = 3
        self.eraser_width = 20

        # history
        self.undo_stack = []
        self.redo_stack = []

        # viewport transform (world <-> screen)
        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.min_scale = 0.2
        self.max_scale = 4.0

        # selection state
        self.selected_strokes = []  # list of Stroke refs
        self._moving_selection = False

        # active drawing state
        self._active_stroke = None
        self._active_eraser = None
        self._shape_start = None
        self._shape_preview = None
        self._sel_start = None
        self._sel_rect = None

        # autosave recovery check before UI built
        self._autosave_present = os.path.exists(AUTOSAVE_FILENAME)

        # UI setup
        self._build_ui()
        # if autosave present, ask recovery
        if self._autosave_present:
            self._prompt_recover_autosave()

        self.new_document()

        # start autosave loop
        self._schedule_autosave()

    # ----------------------------
    # UI
    # ----------------------------

    def _build_ui(self):
        # Menu
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=False)
        filemenu.add_command(label="New", command=self.new_document, accelerator="Ctrl+N")
        filemenu.add_command(label="Open .inks...", command=self.open_inks, accelerator="Ctrl+O")
        filemenu.add_command(label="Save .inks...", command=self.save_inks, accelerator="Ctrl+S")
        filemenu.add_command(label="Export PNG...", command=self.export_png)
        filemenu.add_separator()
        filemenu.add_command(label="Quit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        editmenu = tk.Menu(menubar, tearoff=False)
        editmenu.add_command(label="Undo", command=self.undo, accelerator="Ctrl+Z")
        editmenu.add_command(label="Redo", command=self.redo, accelerator="Ctrl+Y")
        menubar.add_cascade(label="Edit", menu=editmenu)

        helpmenu = tk.Menu(menubar, tearoff=False)
        helpmenu.add_command(label="About", command=lambda: messagebox.showinfo("About", "InkPaint — InkScript editor"))
        menubar.add_cascade(label="Help", menu=helpmenu)

        self.root.config(menu=menubar)
        self.root.bind_all("<Control-n>", lambda e: self.new_document())
        self.root.bind_all("<Control-o>", lambda e: self.open_inks())
        self.root.bind_all("<Control-s>", lambda e: self.save_inks())
        self.root.bind_all("<Control-z>", lambda e: self.undo())
        self.root.bind_all("<Control-y>", lambda e: self.redo())

        # Top toolbar
        toolbar = tk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        # Tool buttons
        tk.Button(toolbar, text="Brush (B)", command=lambda: self.set_tool("brush")).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Eraser (E)", command=lambda: self.set_tool("eraser")).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Line (L)", command=lambda: self.set_tool("line")).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Rect (R)", command=lambda: self.set_tool("rect")).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Ellipse (O)", command=lambda: self.set_tool("ellipse")).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Select (S)", command=lambda: self.set_tool("select")).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Fill (F)", command=lambda: self.set_tool("fill")).pack(side=tk.LEFT)

        tk.Label(toolbar, text="   ").pack(side=tk.LEFT)

        tk.Button(toolbar, text="Add Layer", command=self.add_layer).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Remove Layer", command=self.remove_layer).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Toggle Visible", command=self.toggle_layer_visibility).pack(side=tk.LEFT)

        tk.Label(toolbar, text="   ").pack(side=tk.LEFT)

        tk.Button(toolbar, text="Color", command=self.pick_color).pack(side=tk.LEFT)
        tk.Label(toolbar, text="Size").pack(side=tk.LEFT)
        self.size_slider = tk.Scale(toolbar, from_=1, to=60, orient=tk.HORIZONTAL, command=self._size_changed)
        self.size_slider.set(self.stroke_width)
        self.size_slider.pack(side=tk.LEFT)

        tk.Label(toolbar, text=" ").pack(side=tk.LEFT)
        tk.Button(toolbar, text="Clear Layer", command=self.clear_current_layer).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Flatten & Export PNG", command=self.export_png).pack(side=tk.LEFT)

        # Keyboard shortcuts for tools
        self.root.bind_all("b", lambda e: self.set_tool("brush"))
        self.root.bind_all("B", lambda e: self.set_tool("brush"))
        self.root.bind_all("e", lambda e: self.set_tool("eraser"))
        self.root.bind_all("E", lambda e: self.set_tool("eraser"))
        self.root.bind_all("l", lambda e: self.set_tool("line"))
        self.root.bind_all("L", lambda e: self.set_tool("line"))
        self.root.bind_all("r", lambda e: self.set_tool("rect"))
        self.root.bind_all("R", lambda e: self.set_tool("rect"))
        self.root.bind_all("o", lambda e: self.set_tool("ellipse"))
        self.root.bind_all("O", lambda e: self.set_tool("ellipse"))
        self.root.bind_all("s", lambda e: self.set_tool("select"))
        self.root.bind_all("S", lambda e: self.set_tool("select"))
        self.root.bind_all("f", lambda e: self.set_tool("fill"))
        self.root.bind_all("F", lambda e: self.set_tool("fill"))

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
        # left-click: primary drawing
        self.canvas.bind("<ButtonPress-1>", self.on_pointer_down)
        self.canvas.bind("<B1-Motion>", self.on_pointer_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_pointer_up)
        # right-click drag: pan
        self.canvas.bind("<ButtonPress-3>", self._on_right_down)
        self.canvas.bind("<B3-Motion>", self._on_right_move)
        self.canvas.bind("<ButtonRelease-3>", self._on_right_up)
        # mouse wheel: zoom
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)  # Windows
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)    # Linux scroll up
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)    # Linux scroll down
        self.canvas.bind("<Motion>", self.on_pointer_motion)

        # Keep map of canvas IDs for quick deletion (screen items)
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
        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
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
        self.undo_stack.append(ActionEraseStrokes(layer.id, removed_ids))
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
        self.size_slider.set(v)

    # ----------------------------
    # Coordinate transforms
    # ----------------------------
    def screen_to_world(self, sx, sy):
        """Convert screen coords (event.x, event.y) to world coords (document)."""
        wx = (sx - self.offset_x) / self.scale
        wy = (sy - self.offset_y) / self.scale
        return (wx, wy)

    def world_to_screen(self, wx, wy):
        sx = wx * self.scale + self.offset_x
        sy = wy * self.scale + self.offset_y
        return (sx, sy)

    # ----------------------------
    # Pointer events (draw / select / shapes)
    # ----------------------------

    def on_pointer_down(self, e):
        # Ctrl+Click eyedropper: pick color from stroke under pointer
        if (e.state & 0x0004):  # Control pressed (platform dependent but commonly 0x4)
            picked = self._pick_color_under(e.x, e.y)
            if picked:
                self.color = picked
                self.status_set(f"Picked color {picked}")
            return

        wx, wy = self.screen_to_world(e.x, e.y)
        layer = self._current_layer()
        if not layer:
            return

        # Brush
        if self.tool == "brush":
            sid = f"stroke_{self.stroke_counter}"
            self.stroke_counter += 1
            s = Stroke(sid, self.color, self.stroke_width)
            s.points.append((wx, wy))
            layer.strokes.append(s)
            self._active_stroke = s
            self._canvas_item_map.setdefault(s.id, [])
            self._canvas_draw_point_segment(s, 0)

        # Eraser (records path)
        elif self.tool == "eraser":
            sid = f"eraser_{int(time.time()*1000)}"
            s = Stroke(sid, None, self.eraser_width)
            s.points.append((wx, wy))
            self._active_eraser = s
            self._canvas_item_map.setdefault(s.id, [])

        # Shape tools
        elif self.tool in ("line", "rect", "ellipse"):
            self._shape_start = (wx, wy)
            self._shape_preview = None

        # Select: start selection rectangle or start move if clicking inside existing selection
        elif self.tool == "select":
            self._sel_start = (wx, wy)
            # if clicked inside selection bounding box, start moving selection
            bbox = self._selection_bbox()
            if bbox and bbox[0] <= wx <= bbox[2] and bbox[1] <= wy <= bbox[3] and self.selected_strokes:
                # start moving selection
                self._moving_selection = True
                # take snapshots for undo
                snapshots = []
                for s in self.selected_strokes:
                    snapshots.append((s.id, s.copy_points(), None))  # new_points filled on release
                self._move_snapshots = snapshots
                self._move_last = (wx, wy)
            else:
                # start new select box
                self._moving_selection = False
                self._sel_rect = None

        # Fill tool: set fill on a closed stroke under pointer
        elif self.tool == "fill":
            self._apply_fill_at(wx, wy)

    def on_pointer_move(self, e):
        wx, wy = self.screen_to_world(e.x, e.y)

        # Brush drawing
        if self.tool == "brush" and getattr(self, "_active_stroke", None):
            s = self._active_stroke
            last = s.points[-1]
            s.points.append((wx, wy))
            self._canvas_draw_line_segment_world(last, (wx, wy), s.color, s.width, tag=s.id)

        # Eraser path
        elif self.tool == "eraser" and getattr(self, "_active_eraser", None):
            s = self._active_eraser
            last = s.points[-1]
            s.points.append((wx, wy))
            # draw eraser preview in screen coords (use bg color)
            self._canvas_draw_line_segment_world(last, (wx, wy), self.bg_color, s.width, tag=s.id)

        # Shape preview drawing (we draw preview on canvas in screen coords)
        elif self.tool in ("line", "rect", "ellipse") and getattr(self, "_shape_start", None):
            if self._shape_preview:
                try:
                    self.canvas.delete(self._shape_preview)
                except Exception:
                    pass
            x0, y0 = self._shape_start
            sx0, sy0 = self.world_to_screen(x0, y0)
            sx1, sy1 = self.world_to_screen(wx, wy)
            if self.tool == "line":
                self._shape_preview = self.canvas.create_line(sx0, sy0, sx1, sy1, fill=self.color, width=self.stroke_width)
            elif self.tool == "rect":
                self._shape_preview = self.canvas.create_rectangle(sx0, sy0, sx1, sy1, outline=self.color, width=self.stroke_width)
            elif self.tool == "ellipse":
                self._shape_preview = self.canvas.create_oval(sx0, sy0, sx1, sy1, outline=self.color, width=self.stroke_width)

        # Selection rectangle preview
        elif self.tool == "select" and getattr(self, "_sel_start", None) and not self._moving_selection:
            # draw selection rect on canvas (screen coords)
            if self._sel_rect:
                try:
                    self.canvas.delete(self._sel_rect)
                except Exception:
                    pass
            sx0, sy0 = self.world_to_screen(*self._sel_start)
            sx1, sy1 = self.world_to_screen(wx, wy)
            self._sel_rect = self.canvas.create_rectangle(sx0, sy0, sx1, sy1, outline="#4ade80", dash=(4,2))

        # Move selection
        elif self.tool == "select" and self._moving_selection and getattr(self, "_move_last", None):
            dx = wx - self._move_last[0]
            dy = wy - self._move_last[1]
            if dx == 0 and dy == 0:
                return
            # move all selected strokes by dx,dy in world coords
            for s in self.selected_strokes:
                s.points = [(px + dx, py + dy) for px, py in s.points]
                # update canvas items
                self._canvas_delete_strokes([s.id])
            self._move_last = (wx, wy)
            self._redraw_canvas()

    def on_pointer_up(self, e):
        wx, wy = self.screen_to_world(e.x, e.y)
        layer = self._current_layer()
        if not layer:
            return

        # Finish brush
        if self.tool == "brush" and getattr(self, "_active_stroke", None):
            s = self._active_stroke
            self._active_stroke = None
            self.undo_stack.append(ActionAddStroke(self._current_layer().id, s))
            self.redo_stack.clear()
            self.status_set(f"Stroke added: {s.id} pts={len(s.points)}")

        # Finish eraser: apply erase
        elif self.tool == "eraser" and getattr(self, "_active_eraser", None):
            eraser = self._active_eraser
            self._active_eraser = None
            erased_ids = self._apply_eraser_path(eraser.points, eraser.width)
            if erased_ids:
                self.undo_stack.append(ActionEraseStrokes(self._current_layer().id, erased_ids))
                self.redo_stack.clear()
                self.status_set(f"Erased {len(erased_ids)} stroke(s)")
            else:
                self.status_set("Eraser: nothing hit")

        # Finish shape: commit as stroke
        elif self.tool in ("line", "rect", "ellipse") and getattr(self, "_shape_start", None):
            x0, y0 = self._shape_start
            s_id = f"stroke_{self.stroke_counter}"
            self.stroke_counter += 1
            s = Stroke(s_id, self.color, self.stroke_width)
            if self.tool == "line":
                s.points = [(x0, y0), (wx, wy)]
            else:
                # approximate shape as polyline (ellipse) or rectangle polyline
                if self.tool == "rect":
                    pts = [(x0,y0),(wx,y0),(wx,wy),(x0,wy),(x0,y0)]
                    s.points = pts
                elif self.tool == "ellipse":
                    cx = (x0 + wx) / 2
                    cy = (y0 + wy) / 2
                    rx = abs(wx - x0) / 2
                    ry = abs(wy - y0) / 2
                    steps = max(12, int(24 * max(rx, ry) / 100))
                    pts = []
                    for i in range(steps+1):
                        t = 2*math.pi*i/steps
                        px = cx + rx * math.cos(t)
                        py = cy + ry * math.sin(t)
                        pts.append((px,py))
                    s.points = pts
            self._current_layer().strokes.append(s)
            self.undo_stack.append(ActionAddStroke(self._current_layer().id, s))
            self.redo_stack.clear()
            # cleanup
            if self._shape_preview:
                try:
                    self.canvas.delete(self._shape_preview)
                except Exception:
                    pass
            self._shape_start = None
            self._shape_preview = None
            self._redraw_canvas()

        # Finish select: either compute selection or finish moving
        elif self.tool == "select" and getattr(self, "_sel_start", None):
            if self._moving_selection:
                # finish moving selection: record snapshots for undo
                snapshots = []
                for idx, (sid, old_pts, new_pts) in enumerate(self._move_snapshots):
                    # find stroke current points
                    s = self._find_stroke_by_id(sid)
                    if s:
                        new_points = s.copy_points()
                        snapshots.append((sid, old_pts, new_points))
                act = ActionMoveStrokes(self._current_layer().id, snapshots)
                self.undo_stack.append(act)
                self.redo_stack.clear()
                self._moving_selection = False
                self._move_snapshots = None
                self._move_last = None
                self.status_set(f"Moved {len(snapshots)} stroke(s)")
            else:
                # build selection list from rectangle
                x0, y0 = self._sel_start
                xmin, xmax = sorted([x0, wx])
                ymin, ymax = sorted([y0, wy])
                self.selected_strokes = []
                for s in self._current_layer().strokes:
                    if s.erased:
                        continue
                    for px, py in s.points:
                        if xmin <= px <= xmax and ymin <= py <= ymax:
                            self.selected_strokes.append(s)
                            break
                self.status_set(f"Selected {len(self.selected_strokes)} stroke(s)")
                if self._sel_rect:
                    try:
                        self.canvas.delete(self._sel_rect)
                    except Exception:
                        pass
                self._sel_rect = None
            self._sel_start = None

    def on_pointer_motion(self, e):
        # show coordinates
        wx, wy = self.screen_to_world(e.x, e.y)
        self.status_set(f"Pos: {int(wx)},{int(wy)} | Tool: {self.tool}")

    # ----------------------------
    # Canvas drawing helpers (world-aware)
    # ----------------------------

    def _canvas_draw_line_segment_world(self, p1w, p2w, color, width, tag=None):
        p1s = self.world_to_screen(*p1w)
        p2s = self.world_to_screen(*p2w)
        self._canvas_draw_line_segment(p1s, p2s, color, width, tag)

    def _canvas_draw_line_segment(self, p1s, p2s, color, width, tag=None):
        item = self.canvas.create_line(p1s[0], p1s[1], p2s[0], p2s[1],
                                       fill=color, width=width, capstyle=tk.ROUND, smooth=True, tags=(tag or ""))
        if tag:
            self._canvas_item_map.setdefault(tag, []).append(item)

    def _canvas_draw_point_segment(self, stroke, idx):
        if len(stroke.points) == 1:
            xw, yw = stroke.points[0]
            x, y = self.world_to_screen(xw, yw)
            r = max(1, stroke.width/2) * self.scale
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
                if not stroke.points:
                    continue
                if stroke.fill:
                    # draw filled polygon if enough points
                    if len(stroke.points) >= 3:
                        flat = []
                        for p in stroke.points:
                            sx, sy = self.world_to_screen(*p)
                            flat.extend([sx, sy])
                        self.canvas.create_polygon(flat, fill=stroke.fill, outline=stroke.color if stroke.color else "", width=stroke.width, tags=(stroke.id,))
                        self._canvas_item_map.setdefault(stroke.id, []).append(self.canvas.find_all()[-1])
                if len(stroke.points) == 1:
                    self._canvas_draw_point_segment(stroke, 0)
                else:
                    prev = stroke.points[0]
                    for pt in stroke.points[1:]:
                        self._canvas_draw_line_segment_world(prev, pt, stroke.color, stroke.width, tag=stroke.id)
                        prev = pt

    # ----------------------------
    # Eraser logic (simple hit test)
    # ----------------------------

    def _apply_eraser_path(self, path_points_w, eraser_width):
        if not path_points_w:
            return []
        layer = self._current_layer()
        if not layer:
            return []
        rad = eraser_width / 2.0
        erased_ids = []
        for stroke in list(layer.strokes):
            if stroke.erased:
                continue
            # bbox quick check
            xs = [p[0] for p in stroke.points]
            ys = [p[1] for p in stroke.points]
            if not xs or not ys:
                continue
            # precise check: any point distance
            hit = False
            for ep in path_points_w:
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
    # Selection helpers
    # ----------------------------

    def _selection_bbox(self):
        if not self.selected_strokes:
            return None
        xs = []
        ys = []
        for s in self.selected_strokes:
            for x,y in s.points:
                xs.append(x); ys.append(y)
        return (min(xs), min(ys), max(xs), max(ys))

    # ----------------------------
    # Simple eyedropper: pick nearest stroke color under screen point
    # ----------------------------
    def _pick_color_under(self, sx, sy):
        wx, wy = self.screen_to_world(sx, sy)
        # check current layer strokes first
        for layer in self.layers:
            for s in reversed(layer.strokes):
                if s.erased:
                    continue
                for px, py in s.points:
                    dx = px - wx; dy = py - wy
                    if dx*dx + dy*dy <= max(1, s.width/2)**2:
                        return s.color
        # fallback background
        return self.bg_color

    # ----------------------------
    # Undo / Redo
    # ----------------------------

    def undo(self):
        if not self.undo_stack:
            self.status_set("Nothing to undo")
            return
        act = self.undo_stack.pop()
        if isinstance(act, ActionAddStroke):
            layer = self._layer_by_id(act.layer_id)
            if layer:
                for s in list(layer.strokes):
                    if s.id == act.stroke.id:
                        layer.strokes.remove(s)
                        self._canvas_delete_strokes([s.id])
                        self.redo_stack.append(act)
                        break
        elif isinstance(act, ActionEraseStrokes):
            layer = self._layer_by_id(act.layer_id)
            if layer:
                for sid in act.stroke_ids:
                    for s in layer.strokes:
                        if s.id == sid:
                            s.erased = False
                self.redo_stack.append(act)
        elif isinstance(act, ActionMoveStrokes):
            layer = self._layer_by_id(act.layer_id)
            if layer:
                # restore old points
                for sid, old_pts, new_pts in act.stroke_snapshots:
                    s = self._find_stroke_by_id(sid)
                    if s:
                        s.points = [ (x,y) for (x,y) in old_pts ]
                self.redo_stack.append(act)
        self._redraw_canvas()
        self.status_set("Undo")

    def redo(self):
        if not self.redo_stack:
            self.status_set("Nothing to redo")
            return
        act = self.redo_stack.pop()
        if isinstance(act, ActionAddStroke):
            layer = self._layer_by_id(act.layer_id)
            if layer:
                layer.strokes.append(act.stroke)
                self._redraw_canvas()
                self.undo_stack.append(act)
        elif isinstance(act, ActionEraseStrokes):
            layer = self._layer_by_id(act.layer_id)
            if layer:
                for sid in act.stroke_ids:
                    for s in layer.strokes:
                        if s.id == sid:
                            s.erased = True
                self._canvas_delete_strokes(act.stroke_ids)
                self.undo_stack.append(act)
        elif isinstance(act, ActionMoveStrokes):
            # apply new points
            layer = self._layer_by_id(act.layer_id)
            if layer:
                for sid, old_pts, new_pts in act.stroke_snapshots:
                    s = self._find_stroke_by_id(sid)
                    if s:
                        s.points = [ (x,y) for (x,y) in new_pts ]
                self.undo_stack.append(act)
        self._redraw_canvas()
        self.status_set("Redo")

    def _layer_by_id(self, lid):
        for l in self.layers:
            if l.id == lid:
                return l
        return None

    def _find_stroke_by_id(self, sid):
        for l in self.layers:
            for s in l.strokes:
                if s.id == sid:
                    return s
        return None

    # ----------------------------
    # Save / Load .inks (includes fill)
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
                    for s in layer.strokes:
                        if not s.erased:
                            f.write(f"  draw path id={s.id} {{\n")
                            first = True
                            for x, y in s.points:
                                cmd = "move" if first else "line"
                                f.write(f"    {cmd} {float(x):.2f} {float(y):.2f}\n")
                                first = False
                            f.write("  } ")
                            if s.color:
                                f.write(f"stroke={s.color} ")
                            if s.fill:
                                f.write(f"fill={s.fill} ")
                            f.write(f"strokeWidth={int(s.width)}\n\n")
                        else:
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
        # simple robust parser for draw path / erase ref / fills
        self.layers.clear()
        self.layer_counter = 1
        self.stroke_counter = 1
        current_layer = None
        idx = 0
        n = len(lines)
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
                pts = []
                # consume block
                while idx < n:
                    raw2 = lines[idx]; idx += 1
                    s2 = raw2.strip()
                    if not s2 or s2.startswith("#"):
                        continue
                    if s2.startswith("}"):
                        break
                    parts = s2.split()
                    if parts[0] in ("move", "line") and len(parts) >= 3:
                        try:
                            x = float(parts[1]); y = float(parts[2])
                            pts.append((x, y))
                        except:
                            pass
                # check inline style line after block
                style = {}
                look_idx = idx
                while look_idx < n:
                    nxt = lines[look_idx].strip()
                    if not nxt or nxt.startswith("#"):
                        look_idx += 1
                        continue
                    if "=" in nxt and not re.match(r'^(draw|set|layer|transform|erase|canvas|background)\b', nxt):
                        for token in nxt.split():
                            if "=" in token:
                                k, v = token.split("=", 1)
                                style[k] = v
                        idx = look_idx + 1
                    break
                color = style.get("stroke", "#000000")
                fill = style.get("fill", None)
                width = int(float(style.get("strokeWidth", "2")))
                st = Stroke(sid, color, width, pts, fill=fill)
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
                m = re.search(r'ref=([^\s]+)', line)
                if m:
                    rid = m.group(1)
                    for s in current_layer.strokes:
                        if s.id == rid:
                            s.erased = True
                            break
            else:
                continue

        self._refresh_layer_list()
        self._redraw_canvas()
        self.status_set("Loaded .inks")

    # ----------------------------
    # Export PNG
    # ----------------------------

    def export_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image", "*.png")])
        if not path:
            return
        try:
            img = Image.new("RGBA", (self.width, self.height), self._hex_to_rgb_alpha(self.bg_color))
            draw = ImageDraw.Draw(img)
            for layer in reversed(self.layers):
                if not layer.visible:
                    continue
                for stroke in layer.strokes:
                    if stroke.erased:
                        continue
                    pts = stroke.points
                    if not pts:
                        continue
                    col = self._hex_to_rgb(stroke.color or "#000000")
                    if stroke.fill and len(pts) >= 3:
                        draw.polygon(pts, fill=self._hex_to_rgb(stroke.fill))
                    if len(pts) == 1:
                        x,y = pts[0]
                        r = max(1, stroke.width/2)
                        draw.ellipse([x-r,y-r,x+r,y+r], fill=col, outline=col)
                    else:
                        flat = [coord for p in pts for coord in p]
                        draw.line(flat, fill=col, width=int(stroke.width))
            img.save(path)
            self.status_set(f"Exported PNG: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Export error", str(e))
            self.status_set("Export failed")

    # ----------------------------
    # Helpers: colors, coords
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
    # Mouse wheel zoom & pan
    # ----------------------------

    def _on_mouse_wheel(self, event):
        # determine delta (handle both Windows and Linux)
        delta = 0
        if hasattr(event, "delta"):
            delta = event.delta
        elif event.num == 4:
            delta = 120
        elif event.num == 5:
            delta = -120
        # zoom factor
        if delta > 0:
            factor = 1.1
        else:
            factor = 1/1.1
        # mouse position (screen)
        sx, sy = event.x, event.y
        # world coords before zoom
        wx_before, wy_before = self.screen_to_world(sx, sy)
        # apply scale with clamp
        new_scale = max(self.min_scale, min(self.max_scale, self.scale * factor))
        factor = new_scale / self.scale
        self.scale = new_scale
        # adjust offsets so mouse focus remains stable
        self.offset_x = sx - wx_before * self.scale
        self.offset_y = sy - wy_before * self.scale
        self._redraw_canvas()

    def _on_right_down(self, event):
        # start panning
        self._pan_last = (event.x, event.y)

    def _on_right_move(self, event):
        if getattr(self, "_pan_last", None) is None:
            return
        dx = event.x - self._pan_last[0]
        dy = event.y - self._pan_last[1]
        self.offset_x += dx
        self.offset_y += dy
        self._pan_last = (event.x, event.y)
        self._redraw_canvas()

    def _on_right_up(self, event):
        self._pan_last = None

    # ----------------------------
    # Fill (simple: assign fill to stroke containing the point)
    # ----------------------------
    def _apply_fill_at(self, wx, wy):
        layer = self._current_layer()
        if not layer:
            return
        # find first stroke whose polygon contains point (ray-casting)
        for s in reversed(layer.strokes):
            if s.erased or not s.points or len(s.points) < 3:
                continue
            if self._point_in_polygon((wx,wy), s.points):
                s.fill = self.color
                self.undo_stack.append(ActionAddStroke(layer.id, s))  # treat as change to allow undo (coarse)
                self.redo_stack.clear()
                self._redraw_canvas()
                self.status_set("Fill applied")
                return
        self.status_set("No closed shape found to fill")

    def _point_in_polygon(self, point, polygon):
        # ray-casting algorithm
        x, y = point
        inside = False
        n = len(polygon)
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[(i+1)%n]
            intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi)
            if intersect:
                inside = not inside
        return inside

    # ----------------------------
    # Autosave & recovery
    # ----------------------------
    def _schedule_autosave(self):
        try:
            self._autosave_task = self.root.after(AUTOSAVE_INTERVAL_MS, self._do_autosave)
        except Exception:
            pass

    def _do_autosave(self):
        try:
            # write to temp path
            try:
                with open(AUTOSAVE_FILENAME, "w", encoding="utf-8") as f:
                    f.write("inkscript 1.0\n\n")
                    f.write(f"canvas {self.width} {self.height}\n")
                    f.write(f"background {self.bg_color}\n\n")
                    for layer in self.layers:
                        f.write(f'layer id={layer.id} name="{layer.name}" visible={"true" if layer.visible else "false"} {{\n')
                        for s in layer.strokes:
                            if not s.erased:
                                f.write(f"  draw path id={s.id} {{\n")
                                first = True
                                for x, y in s.points:
                                    cmd = "move" if first else "line"
                                    f.write(f"    {cmd} {float(x):.2f} {float(y):.2f}\n")
                                    first = False
                                f.write("  } ")
                                if s.color:
                                    f.write(f"stroke={s.color} ")
                                if s.fill:
                                    f.write(f"fill={s.fill} ")
                                f.write(f"strokeWidth={int(s.width)}\n\n")
                            else:
                                f.write(f"  erase ref={s.id}\n")
                        f.write("}\n\n")
            except Exception:
                pass
            self.status_set("Autosaved")
        finally:
            self._schedule_autosave()

    def _prompt_recover_autosave(self):
        ans = messagebox.askyesno("Recover", "An autosave file was found. Recover it?")
        if ans:
            try:
                with open(AUTOSAVE_FILENAME, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                self._load_from_lines(lines)
                self.status_set("Recovered from autosave")
            except Exception:
                messagebox.showerror("Recover failed", "Failed to recover autosave file.")
        else:
            try:
                os.remove(AUTOSAVE_FILENAME)
            except Exception:
                pass

    # ----------------------------
    # Helpers
    # ----------------------------

    def _hex_from_rgb_tuple(self, rgb):
        return "#{:02x}{:02x}{:02x}".format(*rgb)

# ----------------------------
# Run
# ----------------------------

if __name__ == "__main__":
    root = tk.Tk()
    app = InkPaint(root)
    root.mainloop()

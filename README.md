# InkScript

**InkScript is a code-based image format for human drawing.**  
It represents images as *intentional actions* — strokes, shapes, layers, and edits — not pixels.

> InkScript treats drawing as source code.

---

## Why InkScript?

Traditional image formats lose intent:

- **PNG/JPG** → pixels only, no structure
- **PSD** → large, binary, proprietary
- **SVG** → great for geometry, poor for freehand drawing

InkScript is different.

It is:
- 📝 **Human-readable**
- 🔁 **Replayable**
- 🧠 **Intent-preserving**
- 🌱 **Version-control friendly**
- 🎨 **Painter-first**

An `.inks` file is not just an image — it is a **visual program**.

---

## What InkScript Looks Like

```inks
inkscript 1.0

canvas 800 600
background #0b0d12

layer id=1 name="paint" visible=true {
  draw path id=stroke_1 {
    move 120 200
    line 160 240
    line 220 300
  } stroke=#ffffff strokeWidth=3

  erase ref=stroke_0
}
```

You can:
- Read it
- Edit it
- Diff it
- Generate it
- Render it

---

## Core Concepts

### 🖌️ Strokes, Not Pixels
Freehand drawing is stored as paths with points and style.

### 🧱 Layers
Layers are explicit, ordered, and named.

### ✏️ Non-Destructive Editing
Erase does not delete — it records intent.

```inks
erase ref=stroke_12
```

### 🔁 Deterministic Rendering
The same file always produces the same image.

### 🔍 Inspectable History
InkScript preserves *how* something was drawn, not just the result.

---

## Use Cases

- 🎨 Digital illustration & sketching
- 🧠 Version-controlled art (Git-friendly)
- 🤝 Collaborative whiteboards
- 🧪 Procedural & generative art
- 🎮 2D game assets
- 📐 Diagrams & education
- 🤖 AI-assisted drawing tools
- 🗄️ Long-term archival of artwork

---

## Project Status

InkScript is **early but functional**.

What exists:
- ✔ `.inks` grammar (v1.0)
- ✔ Python renderer → `.inks` → PNG
- ✔ Paint editor that saves `.inks`
- ✔ Deterministic save/load
- ✔ Non-destructive erase

What’s coming:
- 🔄 Animation & timelines
- 📦 Compiled format (`.inkc`)
- 🌐 Web renderer
- 🧩 Shape & text tools
- 🧠 AI tooling
- 📜 Formal specification

---

## Repository Structure (suggested)

```
/spec        → InkScript grammar & docs
/renderer    → Reference renderers
/editor      → InkScript paint editor
/examples    → Sample .inks files
/tools       → Converters & utilities
```

*(Adjust to your actual repo layout)*

---

## Philosophy

InkScript is built on a few simple beliefs:

- Drawing deserves source code
- Files should be understandable without special software
- Tools should not erase intent
- Art should survive software

Read the full [InkScript Manifesto](MANIFESTO.md).

---

## Contributing

InkScript is open by design.

You can contribute by:
- Writing renderers (any language)
- Improving the editor
- Extending the grammar
- Writing documentation
- Creating example artwork
- Testing edge cases

See `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md`.

---

## License

InkScript is released under the **Server-Lab Open-Control License (SOCL) 1.0**.
See `LICENSE` for the full text.

---

## In One Sentence

> **InkScript is a human-readable image format that stores drawings as code.**

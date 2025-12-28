# The InkScript Manifesto

## We believe drawing deserves source code.

For decades, images have been trapped in pixels or opaque binaries.  
Artists paint, but their intent is lost.  
Edits overwrite history.  
Tools decide what is possible.

InkScript exists to change that.

---

## What InkScript Is

InkScript is a **code-based image format** designed for **human drawing**.

It represents images as **intentional actions**, not pixels:
- A stroke, not a bitmap
- A shape, not a raster
- An erase, not destruction

InkScript is **readable**, **replayable**, and **deterministic**.

An InkScript file is not a picture.  
It is a **visual program**.

---

## What InkScript Is Not

InkScript is not:
- A replacement for PNG or JPG
- A Photoshop clone
- A purely mathematical vector format
- A binary asset container

InkScript does not optimize for compression first.  
It optimizes for **clarity, control, and authorship**.

---

## Core Principles

### 1. Code Is the Source of Truth

Pixels are output, not storage.

Every visible mark must be explainable as code:
```inks
draw path id=stroke_42 {
  move 120 200
  line 180 260
}
```

If it cannot be described, it does not exist.

---

### 2. Human Readability Matters

InkScript files are written for people first.

You should be able to:
- Open a `.inks` file in a text editor
- Understand what was drawn
- Change it by hand
- Learn from it

Visual creation should not be locked behind proprietary formats.

---

### 3. Drawing Is an Accumulation of Intent

InkScript preserves **how** something was made, not just **what** it is.

- Strokes are added
- Shapes are layered
- Erase is non-destructive
- History is append-only

Nothing is silently destroyed.

---

### 4. Determinism Is Non-Negotiable

The same InkScript file must always produce the same image.

Across:
- Machines
- Platforms
- Renderers
- Time

InkScript rendering must be predictable and testable.

---

### 5. Editing Is a First-Class Operation

Undo is not a UI trick.  
Erase is not deletion.

```inks
erase ref=stroke_12
```

Edits are explicit, reversible, and inspectable.

---

### 6. Version Control Is a Feature

InkScript is designed to work with tools like Git.

- Meaningful diffs
- Mergeable drawings
- Reviewable changes
- Blameable strokes

Art deserves the same collaboration tools as code.

---

### 7. Tools Are Replaceable

InkScript does not belong to a single editor.

Any tool may:
- Create InkScript
- Modify InkScript
- Render InkScript

The format is stable.  
The ecosystem is plural.

---

### 8. Procedural and Manual Creation Are Equals

InkScript respects both:
- A hand-drawn brush stroke
- A generated geometric pattern

Code may generate InkScript.  
InkScript may be edited by hand.

There is no hierarchy.

---

### 9. InkScript Is Future-Facing

InkScript is designed to grow without breaking:

- Animation
- Constraints
- Timelines
- Live collaboration
- AI-assisted editing

Extensions must remain readable and composable.

---

### 10. Ownership Is Explicit

An InkScript file belongs to its author.

No hidden metadata.  
No silent tracking.  
No vendor lock-in.

The file says exactly what it contains.

---

## Why InkScript Exists

Because:
- Art should be understandable
- Creativity should be inspectable
- Tools should not erase intent
- Files should survive software

InkScript exists so drawings can be **studied, shared, forked, and preserved**.

---

## The Promise

If you open an InkScript file years from now:
- You will know what was drawn
- You will know how it was drawn
- You will be able to change it

InkScript is not a black box.

---

## The Invitation

InkScript is open.

- Build tools
- Write renderers
- Extend the grammar
- Challenge the design

If you believe images should be more than pixels,
you are already part of this.

---

## In Short

> **InkScript treats drawing as code,  
without taking the humanity out of it.**

That is the line you launch with.

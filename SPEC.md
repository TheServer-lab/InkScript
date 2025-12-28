# InkScript Specification  
**Version 1.0**

---

## 1. Overview

InkScript is a **text-based image description language** for representing drawings as structured, deterministic commands.

An InkScript file (`.inks`) describes:
- Canvas configuration
- Layers
- Drawing primitives
- Styles
- Non-destructive edits

InkScript is designed to be:
- Human-readable
- Deterministic
- Append-friendly
- Version-control compatible

---

## 2. File Encoding

- Text encoding: **UTF-8**
- Line endings: LF (`\n`) or CRLF (`\r\n`)
- Case-sensitive keywords
- Whitespace-insensitive except where noted

---

## 3. File Structure

An InkScript file consists of the following top-level sections **in order**:

```
Header
Canvas
Background
Layer*
```

Formally:

```
InkFile ::= Header Canvas Background LayerBlock+
```

---

## 4. Header

### Syntax

```
inkscript <version>
```

### Grammar

```
Header ::= "inkscript" Version
Version ::= Digit+ "." Digit+
```

### Example

```inks
inkscript 1.0
```

---

## 5. Canvas

### Syntax

```
canvas <width> <height>
```

### Grammar

```
Canvas ::= "canvas" Integer Integer
```

- Width and height are in **pixels**
- Must be positive integers

### Example

```inks
canvas 800 600
```

---

## 6. Background

### Syntax

```
background <color>
```

### Grammar

```
Background ::= "background" Color
```

- Background is rendered beneath all layers

### Example

```inks
background #0b0d12
```

---

## 7. Layers

### Syntax

```
layer <attributes> {
  LayerStatement*
}
```

### Grammar

```
LayerBlock ::= "layer" LayerAttributes "{" LayerStatement* "}"
```

### Required Attributes

| Name     | Type   | Description              |
|----------|--------|--------------------------|
| `id`     | int    | Unique layer identifier  |
| `name`   | string | Human-readable name      |
| `visible`| bool   | Rendering toggle         |

### Grammar

```
LayerAttributes ::= Attribute+
Attribute ::= Identifier "=" Value
```

### Example

```inks
layer id=1 name="sketch" visible=true {
  ...
}
```

---

## 8. Layer Statements

A layer may contain zero or more of the following statements:

```
LayerStatement ::=
    DrawStatement
  | SetStatement
  | TransformStatement
  | EraseStatement
```

---

## 9. Draw Statements

### 9.1 Draw Path

Used for freehand strokes.

#### Syntax

```
draw path <attributes> {
  PathCommand+
} <style>
```

#### Grammar

```
DrawStatement ::= "draw" "path" DrawAttributes "{" PathCommand+ "}" StyleAttributes
```

#### Path Commands

```
PathCommand ::=
    "move" Number Number
  | "line" Number Number
  | "curve" Number Number Number Number Number Number
```

| Command | Description |
|-------|------------|
| `move` | Move pen without drawing |
| `line` | Draw straight line |
| `curve` | Cubic Bézier curve |

#### Example

```inks
draw path id=stroke_1 {
  move 120 200
  line 160 240
  curve 180 260 200 280 220 300
} stroke=#ffffff strokeWidth=3
```

---

### 9.2 Draw Shape (Optional v1.0 Support)

#### Rect

```
draw rect x=<num> y=<num> w=<num> h=<num> <style>
```

#### Circle

```
draw circle cx=<num> cy=<num> r=<num> <style>
```

---

## 10. Style Attributes

Styles may appear:
- Inline after a draw block
- As defaults via `set`

### Grammar

```
StyleAttributes ::= (StyleAttribute)*
StyleAttribute ::= Identifier "=" Value
```

### Standard Style Keys

| Key | Type | Description |
|----|-----|------------|
| `stroke` | Color | Stroke color |
| `strokeWidth` | Number | Stroke thickness |
| `fill` | Color | Fill color |
| `opacity` | Number | 0.0–1.0 |

### Example

```inks
stroke=#ff006e strokeWidth=4
```

---

## 11. Set Statements (Layer Defaults)

### Syntax

```
set <key>=<value>
```

### Grammar

```
SetStatement ::= "set" StyleAttribute
```

### Example

```inks
set stroke=#ffffff
set strokeWidth=2
```

---

## 12. Transform Statements

Transforms apply to previously defined objects.

### Syntax

```
transform ref=<id> <operation>
```

### Grammar

```
TransformStatement ::= "transform" "ref" "=" Identifier TransformOp
TransformOp ::= Rotate | Translate | Scale
```

#### Rotate

```
rotate <angle> cx=<num> cy=<num>
```

#### Translate

```
translate dx=<num> dy=<num>
```

#### Scale

```
scale sx=<num> sy=<num>
```

### Example

```inks
transform ref=logo rotate 15 cx=200 cy=150
```

---

## 13. Erase Statements (Non-Destructive)

Erase marks an object as hidden without deleting it.

### Syntax

```
erase ref=<id>
```

### Grammar

```
EraseStatement ::= "erase" "ref" "=" Identifier
```

### Example

```inks
erase ref=stroke_12
```

---

## 14. Identifiers

### Grammar

```
Identifier ::= Letter (Letter | Digit | "_" | "-")*
```

Identifiers must be unique within their scope.

---

## 15. Values

### Numbers

```
Number ::= Integer | Float
Integer ::= Digit+
Float ::= Digit+ "." Digit+
```

### Booleans

```
Bool ::= "true" | "false"
```

### Strings

```
String ::= "\"" (AnyCharExceptQuote)* "\""
```

---

## 16. Colors

### Supported Formats

- `#RRGGBB`
- `#RGB`

### Grammar

```
Color ::= "#" HexDigit HexDigit HexDigit (HexDigit HexDigit HexDigit)?
```

---

## 17. Comments

### Syntax

```
# This is a comment
```

- Comments may appear on their own line
- Inline comments are not guaranteed to be supported

---

## 18. Determinism Rules

An InkScript renderer **must**:
1. Process statements top-to-bottom
2. Preserve layer order
3. Apply erase and transform after draw
4. Ignore unknown attributes safely

---

## 19. Forward Compatibility

- Unknown commands must be ignored, not fatal
- Unknown attributes must be preserved if round-tripping
- New features must not alter existing semantics

---

## 20. Minimal Valid File

```inks
inkscript 1.0
canvas 1 1
background #000000

layer id=1 name="default" visible=true {
}
```

---

## 21. Design Guarantees

- Text-only
- Append-safe
- Tool-agnostic
- Future-extensible

---

## 22. Versioning Policy

- Major version changes may break compatibility
- Minor versions must be backward-compatible
- Files declare their version explicitly

---

## End of Specification

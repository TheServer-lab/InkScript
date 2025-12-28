# InkScript Compliance Guidelines

This document defines what it means for a tool to be **InkScript-compliant**.

InkScript compliance is about **correctness, determinism, and safety** —
not branding, approval, or centralization.

No tool is required to be “official” to be compliant.

---

## 1. Scope

These guidelines apply to any software that:

- Parses `.inks` files
- Renders InkScript images
- Edits or converts InkScript
- Validates InkScript syntax

Examples:
- Renderers
- Paint editors
- Converters (SVG ↔ InkScript)
- Validators / linters

---

## 2. Levels of Compliance

### 2.1 Syntax Compliance (Required)

A compliant implementation **must**:

- Accept valid InkScript files as defined in `SPEC.md`
- Reject or safely ignore malformed input
- Ignore unknown commands and attributes without crashing
- Preserve parsing order and hierarchy

Must **not**:
- Execute arbitrary code
- Depend on undefined behavior

---

### 2.2 Rendering Compliance (For Renderers)

Renderers **must**:

- Process commands top-to-bottom
- Respect layer order and visibility
- Apply styles deterministically
- Produce identical output for identical input (given same environment)
- Apply transforms and erases after draw statements

Renderers **may**:
- Use different internal representations
- Apply antialiasing or rasterization strategies
- Optimize performance

Renderers **must not**:
- Reorder commands
- Infer missing semantics
- Modify drawing intent

---

### 2.3 Editing Compliance (For Editors)

Editors **must**:

- Preserve semantic meaning when saving
- Retain unknown attributes and commands when round-tripping
- Avoid destructive rewrites unless explicitly requested
- Save files that conform to the declared InkScript version

Editors **should**:
- Preserve user formatting when possible
- Avoid unnecessary reordering or normalization

---

### 2.4 Conversion Compliance (For Converters)

Converters **must**:

- Clearly document any loss of information
- Not invent InkScript semantics
- Preserve IDs where possible
- Emit valid InkScript according to `SPEC.md`

Converters **may**:
- Use approximations when converting from non-equivalent formats
- Emit comments describing limitations

---

## 3. Version Handling

Compliant tools **must**:

- Read the declared `inkscript <version>` header
- Reject or warn when encountering unsupported versions
- Not assume newer features exist in older versions

Forward compatibility rules:
- Unknown commands → ignored
- Unknown attributes → preserved
- Unknown blocks → skipped safely

---

## 4. Error Handling

Compliant tools **must**:

- Fail safely
- Provide meaningful error messages
- Avoid crashes on malformed input

Errors **must not**:
- Corrupt existing files
- Produce partially-written output without warning

---

## 5. Security Requirements

All compliant implementations **must** treat `.inks` files as untrusted input.

At minimum:

- Enforce canvas size limits
- Enforce path/point count limits
- Prevent infinite loops or recursion
- Avoid dynamic code execution
- Avoid file system access unless explicitly intended

Refer to `SECURITY.md` for detailed guidance.

---

## 6. Determinism Rules

For the same `.inks` input:

- Output must be deterministic
- No randomness without explicit user opt-in
- No time-based behavior

Differences due to platform-level rendering (e.g., font engines) must be documented.

---

## 7. Optional Features

Optional features **must**:

- Be clearly documented
- Not alter base InkScript semantics
- Not break compatibility with other tools

Optional features **should**:
- Use explicit keywords
- Be ignorable by non-supporting tools

---

## 8. Claiming Compliance

A tool may claim:

> “InkScript 1.0 compliant (syntax / renderer / editor)”

Only if it satisfies the applicable sections of this document.

Compliance does **not** imply:
- Official endorsement
- Certification
- Trademark rights

---

## 9. Non-Compliance

Examples of non-compliance:

- Crashing on unknown commands
- Rewriting files in incompatible ways
- Reordering draw commands
- Executing embedded scripts
- Ignoring version headers

---

## 10. Relationship to License

InkScript is licensed under the  
**Server-Lab Open-Control License (SOCL) 1.0**.

Compliance does not grant:
- Trademark rights
- Special status
- Ownership claims

---

## 11. Authority

This document is maintained by the Project Owner.

In case of ambiguity:
- `SPEC.md` is authoritative
- The Project Owner’s interpretation is final

---

## 12. Final Statement

InkScript compliance is about **trust**.

A compliant tool:
- Does what the file says
- Does not guess
- Does not surprise the user

That is the contract.

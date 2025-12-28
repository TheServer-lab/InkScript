# Security Policy

## Overview

InkScript is a **text-based image specification**, not a network service.
However, implementations (renderers, editors, converters) may process
untrusted `.inks` files and therefore must be designed with security in mind.

This document defines how security issues should be reported and handled.

---

## Supported Versions

Security fixes are provided on a **best-effort basis** for:

- The latest released specification
- Reference implementations maintained by the project owner

Older versions may not receive fixes.

---

## Reporting a Vulnerability

If you discover a security vulnerability, **do not open a public issue**.

Please report it privately via email:

📧 **serverlabdev@proton.me**

Include:

1. A clear description of the issue
2. A minimal `.inks` file or input that reproduces it (if applicable)
3. Potential impact (crash, DoS, memory exhaustion, etc.)
4. Affected implementation(s), if known

You may use PGP or other secure communication if desired.

---

## What Qualifies as a Security Issue

Examples include, but are not limited to:

- Infinite loops or unbounded recursion from malformed `.inks` files
- Memory exhaustion or CPU denial-of-service vectors
- Arbitrary file access or execution via renderers/editors
- Unsafe parsing of identifiers, paths, or embedded data

Purely aesthetic rendering bugs are **not** security issues.

---

## Disclosure Process

1. Issue is acknowledged privately
2. Impact is assessed
3. Fix is developed and tested
4. Public disclosure occurs **after** a fix is available (when applicable)

Timelines depend on severity and complexity.

---

## Security Design Principles

InkScript implementations are strongly encouraged to:

- Enforce resource limits (canvas size, points per path, recursion depth)
- Reject malformed or ambiguous grammar
- Avoid dynamic code execution
- Treat `.inks` files as **untrusted input**
- Fail safely and deterministically

---

## No Bug Bounty

At this time, InkScript does not offer a paid bug bounty program.
Responsible disclosure is appreciated and credited when appropriate.

---

## Legal

This project is licensed under the **Server-Lab Open-Control License (SOCL) 1.0**.
The software is provided **“AS IS”**, without warranty of any kind.

---

Thank you for helping keep InkScript safe and robust.

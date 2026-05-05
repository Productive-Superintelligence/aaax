# Architecture

AAAX is intentionally narrow. It owns the control plane between applications and the underlying frameworks, not the frameworks themselves.

- [Overview](overview.md) explains the stack and the kernel position.
- [Kernel Functions](kernel-functions.md) maps the code to the six control-plane responsibilities.
- [Framework Boundaries](framework-boundaries.md) defines what remains in `sssn` and `lllm`.

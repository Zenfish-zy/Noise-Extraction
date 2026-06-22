# Noise Evidence Next

Next-generation implementation area.

The current stable application remains in `noise_evidence/`. This folder is reserved for the future Tauri + React + Rust implementation.

## Planned Structure

```text
next/
├─ Cargo.toml                # Rust workspace
├─ desktop/                  # Tauri + React desktop app
├─ crates/
│  ├─ noise-types/           # Shared config, event, report schemas
│  ├─ noise-core/            # Audio processing core
│  └─ noise-cli/             # CLI bridge for tests and integration
└─ fixtures/                 # Sanitized audio and golden JSON/CSV fixtures
```

## Current Commands

```powershell
cargo test --manifest-path next/Cargo.toml
```

## Rules

- Do not import code from `noise_evidence/` directly.
- Use JSON contracts for cross-language comparison.
- Keep fixtures synthetic or sanitized.
- Keep the Python app usable until the Tauri app reaches feature parity.

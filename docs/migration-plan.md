# Migration Plan

This plan migrates from the current Python/PySide6 implementation to a Tauri + React + Rust architecture without breaking the usable app.

## Phase 0: Reference Freeze

Status: in progress.

Goals:

- Keep current Python version runnable.
- Expand regression tests around current behavior.
- Document config and event contracts.

Exit criteria:

- `uv run python -m unittest discover -s tests` passes.
- A minimal fixture set exists.
- Current behavior is documented enough for Rust parity tests.

## Phase 1: Next Skeleton

Status: current phase.

Goals:

- Add `next/` workspace skeleton.
- Add architecture and migration docs.
- Add placeholder Rust crate boundaries.
- Add placeholder desktop app boundary.

Exit criteria:

- Repository has a clear next-generation structure.
- No new build dependencies are required yet.
- Current CI remains green.

## Phase 2: UI Prototype

Goals:

- Create a Tauri 2 + React/TypeScript app under `next/desktop`.
- Build static UI with mock data.
- Implement the calm review workflow:
  - Import surface.
  - Waveform area.
  - Detection settings.
  - Event table.
  - Detail side panel.
  - Export summary.

Exit criteria:

- `pnpm tauri dev` opens the prototype.
- No real audio processing is required.
- UI can render mock events and mode states.

## Phase 3: CLI Bridge

Goals:

- Add `next/crates/noise-cli`.
- Initially call the existing Python reference implementation or consume exported JSON fixtures.
- Let Tauri call a backend command that returns event-like mock/reference data.

Exit criteria:

- Tauri UI can trigger an analyze command.
- Frontend receives progress and results.
- Errors are displayed consistently.

## Phase 4: Rust Core Parity

Goals:

- Implement `noise-types`.
- Implement `noise-core` event detection parity for synthetic fixtures.
- Implement full WAV export and highlight export.
- Implement CSV report export.

Exit criteria:

- Rust unit tests match Python fixture expectations.
- CLI can analyze and export without launching GUI.
- Python and Rust outputs are close enough for event review workflows.

## Phase 5: Replace Processing Backend

Goals:

- Tauri app uses Rust core directly.
- Python app remains available but no longer drives next-generation UI.
- Add Tauri build workflow.

Exit criteria:

- Tauri packaged app imports a real local recording.
- Detect, edit, preview, export flow works end to end.
- Packaged app passes smoke test.

## Phase 6: Release Decision

Goals:

- Decide whether Tauri app becomes primary.
- Keep or archive Python app.
- Write migration notes for users.

Exit criteria:

- Tauri version is at least feature-parity for normal workflows.
- Startup and packaging are better than PyInstaller version.
- User-facing docs are updated.

## Immediate Task List

- [x] Push current Python baseline.
- [x] Add core workflow tests.
- [x] Add CI.
- [x] Add `next/` skeleton.
- [x] Add fixture contract docs.
- [x] Add compilable Rust workspace skeleton.
- [x] Add first Rust CLI JSON contract command.
- [ ] Add Tauri prototype only after skeleton review.

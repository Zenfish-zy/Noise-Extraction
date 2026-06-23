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

Status: complete.

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

Status: complete for live analyze/export review loop, real waveform rendering, and basic local playback.

Goals:

- Create a Tauri 2 + React/TypeScript app under `next/desktop`.
- Build static UI with mock data and Rust synthetic data.
- Implement the calm review workflow:
  - Import surface.
  - Waveform area.
  - Detection settings.
  - Event table.
  - Detail side panel.
  - Export summary.

Exit criteria:

- `pnpm build` passes for the React prototype.
- Tauri shell compiles with a React frontend.
- UI can render mock, synthetic Rust, and common audio analysis events.
- Imported audio renders a real downsampled waveform envelope from the Rust backend.
- Imported audio can be played locally through Tauri's asset protocol, with waveform click-to-seek.

## Phase 3: CLI Bridge

Status: complete for common audio analyze/export commands; Tauri reviewed-event export is wired; still open for progress events.

Goals:

- Add `next/crates/noise-cli`.
- Provide CLI commands for synthetic analysis, common audio analysis, and WAV/CSV export.
- Let Tauri call backend commands that return `AnalyzeResult`.
- Keep JSON output compatible with `docs/data-contracts.md`.

Exit criteria:

- Tauri UI can trigger an analyze command.
- Frontend receives results for synthetic and common audio input (`m4a/mp4/aac`, `mp3`, `wav`, `flac`, `ogg/oga`).
- Errors are displayed consistently.

## Phase 4: Rust Core Parity

Status: current phase.

Goals:

- Implement `noise-types`.
- Implement `noise-core` event detection parity for synthetic fixtures.
- Implement `noise-io` decoding beyond WAV or a documented fallback path.
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
- [x] Add Tauri React desktop prototype.
- [x] Add Rust WAV input boundary and CLI smoke path.
- [x] Wire frontend WAV selection to Tauri/Rust analysis.
- [x] Add Rust export path for full WAV, highlight WAV, and CSV report.
- [x] Wire frontend save dialogs to Tauri/Rust export.
- [x] Support common input formats in the next backend and frontend picker.
- [x] Wire reviewed event keep/delete/manual state into next export.
- [x] Split next import/preprocess from manual event detection.
- [x] Render real waveform envelopes for imported audio in the Next UI.
- [x] Add basic local playback and waveform click-to-seek in the Next UI.
- [ ] Add parity fixtures against Python reference output.

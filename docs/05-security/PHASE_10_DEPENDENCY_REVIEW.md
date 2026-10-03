# Phase 10 dependency review

Scanned on 2026-09-30 (Asia/Kolkata) using the npm, uv and Cargo lockfiles.

- npm audit reported zero known vulnerabilities. Installing axe-core subsequently also reported zero.
- pip-audit 2.10.1 checked 64 installed dependencies and reported zero known vulnerabilities.
- cargo-audit 0.22.2 checked 439 locked dependencies: no vulnerability-class errors, seven informational warnings. No advisory is suppressed in repository configuration.

## Remaining upstream warnings

- `proc-macro-error` 1.0.4: unmaintained, RUSTSEC-2024-0370.
- `unic-char-property` 0.9.0: unmaintained, RUSTSEC-2025-0081.
- `unic-char-range` 0.9.0: unmaintained, RUSTSEC-2025-0075.
- `unic-common` 0.9.0: unmaintained, RUSTSEC-2025-0080.
- `unic-ucd-ident` 0.9.0: unmaintained, RUSTSEC-2025-0100.
- `unic-ucd-version` 0.9.0: unmaintained, RUSTSEC-2025-0098.
- `glib` 0.18.5: VariantStrIter iterator soundness warning, RUSTSEC-2024-0429.

The UNIC dependency chain comes through `urlpattern` and Tauri utilities. `cargo tree --target aarch64-apple-darwin -i glib` returned no dependency path: glib is absent from this macOS target graph. That does not clear a Linux release. Linux distribution remains blocked on resolving or explicitly reviewing the glib advisory and platform testing. Replacing incompatible transitive versions without testing is not a verified fix.

The current artifact is an ad-hoc signed local macOS simulation build. Production release review must reconsider these warnings for the actual target graph, adopt compatible upstream fixes, and rerun all checks. Scanner success does not establish the absence of security defects.

Reproduce using `npm run security:scan` after installing cargo-audit in the active Rust toolchain. CI runs all three scanners and keeps warnings visible.

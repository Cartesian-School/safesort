# Changelog

All notable changes to this project are documented in this file.

## [0.1.0]

### Added

- `scan`, `plan`, `apply`, `duplicates`, `undo` commands
- directory scanner with configurable exclusions (`.git`, `.venv`, the
  destination folder, SafeSort's own state folder), symlinks never
  followed
- extension-based file classification with a configurable category
  mapping
- dry-run planning: `plan` describes every move `apply` would make
  without changing anything
- collision-safe apply: destination name conflicts get a free name
  instead of a silent overwrite, both against disk and within one plan
- JSON operation manifest recorded on every `apply`, used by `undo` to
  restore files to their original location (refusing to overwrite
  anything that reappeared there)
- duplicate detection: size prefilter, chunked SHA-256, byte-by-byte
  confirmation of every digest match — read-only, no delete code path
- optional `safesort.toml` configuration (destination name, exclusions,
  extension categories), with built-in defaults when absent
- `logging`-based diagnostics separate from the `print()`-based
  command summaries

### Safety

- default behavior never modifies a file
- `apply` and `undo` are the only commands that touch disk
- no automatic duplicate deletion
- no silent overwrite of an existing file, ever

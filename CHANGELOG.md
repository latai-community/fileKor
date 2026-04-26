# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **CLI**: `filekor status --dir --verbose` shows indexed count and source indicators
- **CLI**: `filekor labels/summary/sidecar` emit events for `--watch` mode
- **Library**: `indexed_in_db` field in `DirectoryStatus` model

### Changed
- **Library**: `get_file_status()` now uses database-first approach with fallback to filesystem
- **Library**: `get_directory_status()` shows accurate status regardless of merged.kor
- **CLI**: `filekor status` now correctly detects files indexed in database via merged.kor
- **CLI**: Removed `--verbose` flag from `status` command (minimal benefit)
- **CLI**: Removed `--watch` flag from `status` command (not functional)
- **CLI**: `filekor status` shows `[DB+FS]`, `[DB only]`, `[FS only]` indicators
- **CLI**: `filekor sync` now finds .kor files in all .filekor/ subdirectories

### Fixed
- **CLI**: `filekor status` incorrectly showed "Files without .kor" when files were in merged.kor
- **CLI**: Fixed timestamp parsing issues in database for Python 3.12
- **CLI**: `_auto_sync_hook()` silently swallowed errors — now shows warning
- **Library**: `file_status_to_dict()` renamed from `summarize()` to avoid CLI naming conflict

### Removed
- **Library**: Removed `summarize()` — use `file_status_to_dict()` instead (breaking change)

---

## [0.1.1] - 2024-04-20

### Added
- Initial release

[Unreleased]: https://github.com/anomalyco/filekor/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/anomalyco/filekor/releases/tag/v0.1.1
# Changelog

All notable changes to BridgAI are documented in this file.

The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses semantic versioning for public releases.

## [Unreleased]

### Planned

- Release automation improvements
- Broader cross-platform GUI validation
- Packaged desktop distributions

## [1.0.0] - 2026-06-16

### Added

- Stable public name: **BridgAI**
- PySide6 desktop interface
- Localhost web interface
- Structured Super-Report generation
- Controlled `#scarica` export workflow
- ZIP, patch, and complete-file analysis
- Unified diff previews
- Transactional apply operations
- Persistent backups and explicit rollback
- Detected project test execution
- Session history with post-apply test results
- Optional `commit-message.md` metadata in AI-generated ZIP archives
- Commit drafts generated from the actual Git working tree and applied-session notes
- Explicitly reviewed and confirmed Git staging and commit creation
- Local Git tools
- GitHub CLI integration
- Optional Google Drive workflow
- Italian and English interface
- Light and dark themes
- Cross-platform launch scripts

### Security

- Workspace target validation
- Sensitive-path blocking
- ZIP traversal protection
- Archive limits
- Explicit user approval before filesystem changes
- No Git staging, commit, pull, merge, or push without explicit user action and confirmation

### Compatibility

The public application name changed to BridgAI. The historical Python package name `local_ai_bridge`, existing entry points, and existing application data locations remain available for backward compatibility.

## Development history

BridgAI has been developed iteratively through its own controlled workflow. The early 0.1 application was used to inspect, review, and apply the changes that progressively produced the 1.0 release, including the commit-message workflow documented here.

## Historical release notes

Detailed notes for the pre-1.0 releases remain available in the `AGGIORNAMENTO_*.md` files.

# Toolz — Repository Instructions

Follow the global Codex instructions first.

## Project constraints

- Python utility repository: favor small, explicit, dependable tools over unnecessary framework complexity.
- Preserve CLI/API behavior unless the roadmap or task explicitly permits breaking changes.
- Keep dependencies minimal and justified.
- Cross-platform filesystem/process behavior should be considered when tools are intended for Windows and Linux.

## Repository workflow

- Inspect existing scripts/modules, dependency metadata, entry points, README, and CI before substantial changes.
- Add focused tests for parsing, filesystem operations, destructive actions, and previously observed bugs where practical.

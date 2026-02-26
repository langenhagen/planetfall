# AGENTS.md

Practical guidance for humans and coding agents working in this repository.

## Intent

- Keep changes small, reviewable, and aligned with existing repo conventions.
- Prefer reliable, non-interactive commands and deterministic output.
- Assume files may change while you work; re-read before final writes and commits.
- Search the web liberally and proactively when debugging or investigating or checking on how an API works.
- Add comments and explicit entity/part names liberally in game/runtime code
  so scene structure is easy to inspect and debug.
- Avoid over-engineering: prefer the simplest solution that keeps behavior
  clear, maintainable, and testable.
- Prefer smaller, modular files over monolithic files when adding or refactoring code.
- Capitalize Markdown headlines (prefer Title Case).

## Project Stack

- Language: Python.
- Runtime/version management: `pyenv`.
- Package/dependency/task workflow: `uv`.
- Game runtime: `ursina`.
- Test framework: `pytest`.
- Lint/format: `ruff`.
- Type checking: `mypy`.
- Security/static scan: `semgrep`.

## Repo Layout

- `planetfall/`: application package.
- `tests/`: unit and integration tests.
- `pyproject.toml`: project metadata and tool configuration.
- `.python-version`: pinned Python version for `pyenv`.

## Local Workflow

Prefer repo-local, reproducible commands:

- Sync dependencies: `uv sync`.
- Run app entrypoint (game): `uv run planetfall`.
- Consider using `scripts/debug-startup.sh` and then inspecting `__debug/out.log` to spot startup issues and logs quickly.
- For visual debugging and reproducible gameplay checks, use:
  - `scripts/capture-game.sh` for timestamped run folders under `__debug/`
    with `screens/`, `capture.log`, and optional `game.log`.
  - `scripts/capture-window.sh` for generic X11 window capture by name/id.
  - `xdotool` in conjunction with capture scripts to automate mouse and keyboard input scenarios while collecting screenshots/logs.
- Run tests: `uv run pytest`.
- Run linter: `uv run ruff check .`.
- Run dead-code sweep liberally: `uv run vulture planetfall/`.
- Run security scan: `uv run --group lint semgrep --config=p/ci --error --metrics=off planetfall tests`.
- Format code: `uv run ruff format .`.
- Run type checks: `uv run mypy planetfall`.
- Run TOML checks/formatting: `taplo check .` and `taplo fmt .`.
- Install hooks: `uv run pre-commit install`.
- Run hooks manually: `uv run pre-commit run --all-files`.
- For shell scripts, run:
  - `shellcheck -x --exclude SC2059 <path/to/script.sh>`
  - `shfmt --indent 4 --write <path/to/script.sh>`
- Optional extended lint checks: `uv run --group lint pylint planetfall tests`.
- Optional personal lint sweep: `source .venv/bin/activate && l3`.
- Optional personal autofix pass: `source .venv/bin/activate && rf`.
- You can scope those tools to one file when iterating quickly:
  - `source .venv/bin/activate && l3 path/to/file.py`
  - `source .venv/bin/activate && rf path/to/file.py`

Note: `l3` runs many tools and is slow. Use it sparingly, typically near
milestones or before committing broader changes.

Do not run full test suites automatically unless requested; use focused checks for touched files/areas first.

## User Shorthand Conventions

Interpret these tokens as explicit workflow commands:

- `prose`
  - Provide a clear prose walkthrough of the topic or changes.
  - Prioritize rationale, tradeoffs, and how pieces fit together.

- `eli5`
  - Provide an Explain Like I am 5 explanation of the current issue.
  - Keep it short, concrete, and technically correct.

- `sw`
  - Explicitly search the web before answering.
  - Use web results as supporting context in the response.

- `mc`, `cm`, or `commit`
  - Create at least one git commit.
  - Commit message must follow this structure:
    - First line: short summary (50 chars or less), imperative mood.
    - Second line: blank.
    - Optional body wrapped to about 72 chars with normal newlines (not with `\n`).
  - Do not use prefixes like `fix:`, `feat:`, `chore:`.
  - Include both the commit message and a prose walkthrough of what changed and why.

- `bigcheck` or `big check`
  - Run and act on this full local sweep:
    - `source .venv/bin/activate; rf; l3; pre-commit run --all; pytest`
  - Treat failures as actionable, fix them, and re-run until green when feasible.

## Commit Workflow Expectations

When asked to commit:

1. Inspect `git status`, full diff, and recent commit style.
2. Stage only relevant files.
3. Run focused checks for touched areas.
4. Commit with a plain imperative summary line, no Conventional Commit prefix.
5. Report commit hash, message, and a short prose walkthrough.

Commit message DO:

- Start the summary in imperative mood (for example `Add`, `Fix`, `Change`).
- Keep the second line blank.
- Wrap body text to about 72 columns.
- Use real line breaks in the body; do not pass wrapped text as one line.
- When using shell commits, prefer multiline `-m $'line1\nline2'` or a
  heredoc body so line wraps are preserved.
- Use simple line wraps in the body and keep one paragraph by default.
- Add extra blank lines only when you intentionally start a new paragraph.

Commit message DON'T:

- Do not use Conventional Commit prefixes.
- Do not end the summary line with a period.
- Do not include literal `\n` text in commit messages; use real newlines.

Before finalizing a commit, verify formatting with:

- `git log -1 --pretty=%B`
- Ensure no body line exceeds roughly 72 characters.

Never include secrets in commits (`.env*`, tokens, private keys, auth dumps).

## Git and Editing Safety

- Do not revert unrelated user changes.
- Do not use destructive git commands unless explicitly requested.
- Avoid interactive commands in automation.
- If a patch fails or context looks stale, re-read files before retrying.

## Linter Pragmas

- Keep linter suppressions (`noqa`, `nosec`, `type: ignore`, pylint disables)
  as narrow as possible.
- Always document each suppression inline with both:
  - the rule meaning (for example `B009: getattr-with-constant`), and
  - a short local reason for why suppression is needed.
- Prefer config-level ignores for broad patterns (for example `tests/**/*.py`)
  over repeated inline suppressions.

## Output Character Policy

- Prefer plain ASCII in output and docs unless a file already requires Unicode.
- Avoid fancy punctuation and hidden/special spacing characters.
- Normalize pasted external text to plain characters before finalizing.

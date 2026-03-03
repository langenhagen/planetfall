#!/usr/bin/env bash
# full-lint - lint Python 3 files
#
# Call flake8, pylint, ssort, ruff, mypy, ty, bandit, black, isort, vulture and refurb
# one after another for a single file.
# Report issues, but don't change the files.
#
# Usage:
#
#   full-lint.sh <FILE>
#
# author: andreasl
shopt -s globstar

files=()

while [ "$#" -gt 0 ]; do
    files+=("$1")
    shift
done

if [ ${#files[@]} -eq 0 ]; then
    printf 'error: missing file argument\n' >&2
    printf 'usage: full-lint.sh <FILE>\n' >&2
    exit 2
fi

if [ ${#files[@]} -gt 1 ]; then
    printf 'error: only one file argument is supported\n' >&2
    printf 'usage: full-lint.sh <FILE>\n' >&2
    exit 2
fi

# normal mode error code specification

pylint_ignores="--disable=C0103"

# warning: `one-blank-line-before-class` (D203) and `no-blank-line-before-class` (D211) are
# incompatible. Ignoring `one-blank-line-before-class`.
# warning: `multi-line-summary-first-line` (D212) and `multi-line-summary-second-line` (D213)
# are incompatible. Ignoring `multi-line-summary-second-line`.
# D205: 1 blank line required between summary line and description
# FA102: Missing `from __future__ import annotations`, but uses PEP 585 collection
# see: https://beta.ruff.rs/docs/rules/
ruff_selection='--select=ALL --ignore=D203,D205,D213,FA102'

flake8_version="$(uv run flake8 --version | head -1 | cut -d' ' -f1)"
ssort_version="$(uv run ssort --version | cut -d' ' -f2)"
pylint_version="$(uv run pylint --version | head -1 | cut -d' ' -f2)"
ruff_version="$(uv run ruff --version | cut -d' ' -f2)"
mypy_version="$(uv run mypy --version | cut -d' ' -f2)"
ty_version="$(uv run ty --version | cut -d' ' -f2)"
bandit_version="$(uv run bandit --version | head -1 | cut -d' ' -f2)"
black_version="$(uv run black --version | cut -d' ' -f2-)"
isort_version="$(uv run isort --version-number)"
vulture_version="$(uv run vulture --version | cut -d' ' -f2)"
refurb_version="$(uv run refurb --version | head -1 | cut -d' ' -f2)"

for file in "${files[@]}"; do
    printf '\e[1;96m=== %s ===\e[m\n' "$file"

    printf '*** flake8 %s ***\n' "$flake8_version"
    uv run flake8 --max-line-length 88 "$file"

    printf '*** ssort %s ***\n' "$ssort_version"
    uv run ssort --check "$file"

    printf '*** ruff %s ***\n' "$ruff_version"
    # shellcheck disable=SC2086
    uv run ruff check ${ruff_selection} "$file"

    printf '*** pylint %s ***\n' "$pylint_version"
    # shellcheck disable=SC2086
    uv run pylint \
        --msg-template='{path}:{line}: {msg_id} {symbol} {msg}' \
        --score=no \
        ${pylint_ignores} \
        "$file"

    printf '*** mypy %s ***\n' "$mypy_version"
    uv run mypy \
        --follow-imports=skip \
        --ignore-missing-imports \
        --no-color-output \
        --no-error-summary \
        --show-error-codes \
        --check-untyped-defs \
        "$file"

    printf '*** ty %s ***\n' "$ty_version"
    uv run ty check

    printf '*** bandit %s ***\n' "$bandit_version"
    uv run bandit \
        --quiet \
        --format custom \
        --msg-template '{relpath}:{line}: {test_id} {msg} {severity} severity, {confidence} confidence  {range}' \
        "$file"

    printf '*** black %s ***\n' "$black_version"
    uv run black --check --quiet "$file" || printf 'The black formatting is bad\n'

    printf '*** isort %s ***\n' "$isort_version"
    uv run isort --profile black --check-only --diff "$file"

    printf '*** vulture %s ***\n' "$vulture_version"
    uv run vulture --min-confidence 100 "$file"

    printf '*** refurb %s ***\n' "$refurb_version"
    uv run refurb --ignore FURB115,FURB149 "$file"
done

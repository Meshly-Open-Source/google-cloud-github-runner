# Recipes for the meshly.ai soft fork of google-cloud-github-runner.
#
# This file is OURS — a fork addition, not a vendor path. It must never appear
# in a pull request to upstream, which has its own conventions and did not ask
# for a task runner.
#
# Everything here is read-only or local. Nothing deploys, nothing applies
# infrastructure, and nothing writes to a meshly repository — the last one is
# also enforced by .claude/hooks/no-meshly-writes.sh, because an instruction
# that only lives in a comment is an instruction with no gate.

set shell := ["bash", "-uc"]

# Detected rather than hardcoded. `python` is not on PATH on every machine --
# it is not on this one -- and a recipe that works only in the author's shell
# is a recipe that fails for the next person with exit 127 and no explanation.
PY := `command -v python3 || command -v python || echo python3`
# For the one script with a third-party dependency (PyYAML). uv keeps it out of
# the global environment; without uv the script itself exits 2 and says how to
# install it, rather than failing with an ImportError traceback.
PYYAML := `if command -v uv >/dev/null 2>&1; then echo "uv run --with pyyaml python"; else command -v python3 || echo python3; fi`
# Prefer an interpreter that ALREADY has pytest -- upstream's
# requirements-dev.txt installs it, so a contributor who followed the project's
# own setup has it on `python`. Only fall back to uv when it is absent, so this
# does not force a tool upstream never asked for onto someone who is set up
# correctly. Detected by importing it, not by guessing from the path.
PYTEST := `if python3 -c 'import pytest' >/dev/null 2>&1; then echo "python3 -m pytest"; elif python -c 'import pytest' >/dev/null 2>&1; then echo "python -m pytest"; elif command -v uv >/dev/null 2>&1; then echo "uv run --with pytest python -m pytest"; else echo "python3 -m pytest"; fi`

# Show the available recipes.
default:
    @just --list --unsorted

# --- verification -------------------------------------------------------------

# Everything a change here must pass. The one command to run before a push.
check: test lint boundary
    @echo "check: OK"

# The IP allowlist's proof command.
#
# The directory is passed EXPLICITLY and that is not redundant: `testpaths` is
# resolved against pytest's inferred rootdir, which differs between a bare run
# and one with arguments. A bare run resolves it to the PROJECT's suite, which
# needs Flask installed and fails collection — an environment failure that
# looks like a fork failure. A proof command that only works when invoked one
# particular way is not a proof command.

# Run the IP allowlist test suite (the proof command).
test:
    {{PYTEST}} -c ipfilter/pytest.ini ipfilter/tests

# Upstream's own style rules, not an imported toolchain. See CONTRIBUTING.md:
# this fork deliberately adds no linters, formatters or scanners to a
# volunteer codebase.

# Lint with UPSTREAM's flake8 rules; no extra tooling.
lint:
    #!/usr/bin/env bash
    set -uo pipefail
    if python3 -c 'import flake8' >/dev/null 2>&1; then
        python3 -m flake8 --max-line-length=127 --extend-ignore=W292,W503 ipfilter/ scripts/
    elif command -v flake8 >/dev/null 2>&1; then
        flake8 --max-line-length=127 --extend-ignore=W292,W503 ipfilter/ scripts/
    elif command -v uv >/dev/null 2>&1; then
        uv run --with flake8 python -m flake8 --max-line-length=127 --extend-ignore=W292,W503 ipfilter/ scripts/
    else
        echo "lint: CANNOT ANALYZE — flake8 not available." >&2
        echo "  pip install -r requirements-dev.txt   (upstream pins it there)" >&2
        echo "  Treat this as RED: a lint that could not run is not a clean lint." >&2
        exit 2
    fi

# Assert the fork has edited no upstream CODE path.
#
# The authoritative check is scripts/upstream_tree_divergence_check.py in
# meshly-infra, which compares git object ids against a recorded baseline. That
# lives there because it governs the submodule pin. This is the cheap local
# version: it names what differs from upstream so you see it before a push
# rather than in CI.
#
# Exit code is read from git directly, never through a pipe — `cmd | tail; echo
# $?` reports tail's status and has produced wrong claims before.

# Assert no upstream CODE path was edited (0 clean / 1 findings / 2 cannot analyze).
boundary:
    #!/usr/bin/env bash
    set -uo pipefail
    if ! git rev-parse --verify --quiet upstream/master >/dev/null; then
        echo "boundary: CANNOT ANALYZE — no upstream/master ref." >&2
        echo "  git remote add upstream https://github.com/Cyclenerd/google-cloud-github-runner" >&2
        echo "  git fetch upstream" >&2
        echo "  Treat this as RED, not clean: with no vendor ref there is nothing to compare." >&2
        exit 2
    fi
    changed=$(git diff --name-only upstream/master...HEAD)
    if [[ -z "$changed" ]]; then
        echo "boundary: CANNOT ANALYZE — zero changed paths vs upstream/master." >&2
        echo "  Either the branch is at the vendor commit, or the comparison is wrong." >&2
        echo "  'Nothing differs' is trivially true of nothing." >&2
        exit 2
    fi
    # Workflows: our own ADDITIONS are fine, EDITS to upstream's are not.
    #
    # The earlier version of this check refused every path under
    # .github/workflows/, which conflated two different things and cost us the
    # ability to dogfood. Editing upstream's ci.yml changes what runs on their
    # code with a repository token and would travel into any PR we send them.
    # Adding meshly-ci.yml is OUR workflow on OUR code, and upstream's lints
    # only app/ and tests/ — so without it everything this fork adds has no CI
    # at all.
    #
    # The meshly- prefix is the discriminator: provenance is obvious in a file
    # listing, and it is trivially excluded from an upstream PR.
    wf=$(echo "$changed" | { grep '^\.github/workflows/' || true; })
    if [[ -n "$wf" ]]; then
        bad=""
        while IFS= read -r f; do
            [[ -z "$f" ]] && continue
            # An ADDED file does not exist in upstream's tree.
            if git cat-file -e "upstream/master:$f" 2>/dev/null; then
                bad="$bad$f (edits a workflow upstream owns)\n"
            elif [[ "$(basename "$f")" != meshly-* ]]; then
                bad="$bad$f (added, but not named meshly-*.yml)\n"
            fi
        done <<< "$wf"
        if [[ -n "$bad" ]]; then
            echo "boundary: FINDINGS — workflow changes that are not permitted:" >&2
            printf "%b" "$bad" | sed 's/^/    /' >&2
            echo "  Our own workflows must be ADDED as .github/workflows/meshly-*.yml." >&2
            echo "  Upstream's workflows are never edited — send that change upstream." >&2
            exit 1
        fi
        echo "boundary: note — permitted workflow additions:"
        echo "$wf" | sed 's/^/    /'
    fi
    # Declared doc divergences, plus the paths the fork owns.
    allowed='^(README\.md|CONTRIBUTING\.md|SECURITY\.md|AGENTS\.md|CLAUDE\.md|AGENTS-LOCAL\.md|RUNNER\.xml|justfile|ipfilter/|docs/|scripts/|\.claude/|\.github/(ATTRIBUTION\.md|ISSUE_TEMPLATE/|PULL_REQUEST_TEMPLATE\.md|FUNDING\.yml|workflows/meshly-)|CHANGELOG\.md)'
    unexpected=$(echo "$changed" | { grep -Ev "$allowed" || true; })
    if [[ -n "$unexpected" ]]; then
        echo "boundary: FINDINGS — upstream paths changed that the fork does not own:" >&2
        echo "$unexpected" | sed 's/^/    /' >&2
        echo "  Send the change upstream, or do it by composition. See AGENTS-LOCAL.md." >&2
        exit 1
    fi
    echo "boundary: OK — $(echo "$changed" | wc -l | tr -d ' ') changed path(s), all fork-owned or declared."
    echo "$changed" | sed 's/^/    /'

# Prove the hooks still bite. Both hook suites, exit codes read directly.
test-hooks:
    #!/usr/bin/env bash
    set -uo pipefail
    rc=0
    for t in .claude/hooks/tests/test_*.sh; do
        printf '%s ... ' "$(basename "$t")"
        if bash "$t" >/tmp/hook-$$.out 2>&1; then
            echo "$(tail -1 /tmp/hook-$$.out)"
        else
            echo "FAILED"; cat /tmp/hook-$$.out; rc=1
        fi
    done
    rm -f /tmp/hook-$$.out
    exit $rc

# Validate every issue-template frontmatter. A malformed one does not error —
# GitHub just stops offering the template, silently.

# Validate issue-template frontmatter parses and is complete.
test-templates:
    {{PYYAML}} scripts/check_issue_templates.py

# --- handoff ------------------------------------------------------------------

# Sanitize AGENTS-LOCAL-USER.md and print a prompt for a MESHLY agent.
#
# This session cannot write to meshly repositories, so meshly-side work leaves
# here as a prompt that a meshly agent executes in its own repo, under its own
# hooks and gates. Copy the output into that session.
#
# The operator's personal details (a personal domain, a residential IP and its
# reverse DNS) are redacted; meshly's own repo and org names are NOT, because
# the destination is a private repo and stripping them would make the handoff
# useless. Secrets are refused outright rather than redacted. The redaction is
# verified against the OUTPUT, so a pattern that failed to substitute refuses
# instead of leaking.

# Print a sanitized handoff prompt for a MESHLY agent to run in its own repo.
export-handoff:
    @{{PY}} scripts/export_handoff.py --source AGENTS-LOCAL-USER.md --out -

# Same, to a file under /tmp for a long handoff.
export-handoff-file:
    @{{PY}} scripts/export_handoff.py --source AGENTS-LOCAL-USER.md --out /tmp/meshly-handoff.md
    @echo "Copy /tmp/meshly-handoff.md into a meshly agent session." >&2

# Show what WOULD be redacted, without emitting the prompt body.
export-handoff-dry:
    @{{PY}} scripts/export_handoff.py --source AGENTS-LOCAL-USER.md --out /dev/null

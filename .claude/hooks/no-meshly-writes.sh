#!/bin/bash
# Refuse any WRITE to a meshly repository from an agent working in this fork.
#
# WHY
# ---
# This repository is public and upstream-facing. The meshly repos are private,
# and the two have different review paths, different gates and different
# approvers. An agent that holds both in context will, sooner or later, "just
# fix" something on the meshly side while it is here — and that change arrives
# in a private repo with none of its gates applied, authored by whoever happened
# to be driving this session.
#
# jw, 2026-10-02: "you, in this session, do not touch any meshly repos."
#
# The division of labour is deliberate: work in the fork happens here, and
# anything the meshly side needs is handed over as a PROMPT a meshly agent
# executes in its own repo, under its own hooks. `just export-handoff` produces
# that prompt. A handoff reviewed by the receiving agent is strictly better than
# a cross-repo write nobody gated.
#
# WHAT IS BLOCKED
# ---------------
# Writes whose target is under a meshly checkout. READS ARE FINE AND STAY FINE —
# an agent here legitimately needs to look at meshly-infra to know what the
# consumer expects, and blocking that would just push it to guess.
#
# So the test is on the VERB, not the path alone: a mutating command plus a
# meshly path is a block; a meshly path on its own is not.
#
# HONEST LIMITATION
# -----------------
# This is a denylist of mutating verbs. A write performed by a verb nobody
# listed gets through — a python one-liner, a text editor, an `sh -c` that
# builds the path at runtime. It is a speed bump against the realistic mistake
# (an agent reflexively running `git commit` in the wrong tree), not a sandbox.
# The real boundary is the instruction; this catches the common slip.
#
# ESCAPE HATCH
#   MESHLY_WRITE_INTENDED=1   greppable in the transcript, and you should be
#                             able to say why in the same breath.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

if [[ -z "$COMMAND" ]]; then
  echo '{"decision":"approve"}'
  exit 0
fi

if [[ -n "${MESHLY_WRITE_INTENDED:-}" || "$COMMAND" == *MESHLY_WRITE_INTENDED=* ]]; then
  echo '{"decision":"approve"}'
  exit 0
fi

# Quoted spans are stripped before matching, so a grep or an echo that merely
# MENTIONS a meshly path is not treated as a write. A guard that fires on
# mentions trains the next agent to use the escape hatch reflexively, and a
# reflexive escape hatch is the same as no guard.
SCRUBBED=$(printf '%s' "$COMMAND" | sed -e "s/'[^']*'//g" -e 's/"[^"]*"//g')

# Any path that lands inside a meshly checkout, including the worktrees that
# live beside it (.wt-*, .git-worktrees/) and the submodules under it.
MESHLY_PATH='(/home/jw/dev/meshly|~/dev/meshly|\.\./meshly|meshly-infra|meshly-backend|meshly-frontend|meshly-compliance|meshly-product|\.wt-[a-z0-9-]+|\.git-worktrees)'

# Mutating verbs. git subcommands are listed individually because `git` itself
# is overwhelmingly used for reads here (status, log, diff, show, ls-tree).
WRITE_VERB='(^|[^[:alnum:]_-])(rm|mv|cp|install|truncate|tee|dd|chmod|chown|ln|mkdir|rmdir|sed[[:space:]]+-[a-zA-Z]*i|perl[[:space:]]+-[a-zA-Z]*i)([[:space:]]|$)'
# Any number of intervening tokens between `git` and the subcommand, because
# the realistic form is `git -C <path> commit` — a flag WITH A VALUE. Matching
# only `-flag` tokens let every `git -C ... commit` through, which is the exact
# shape an agent uses to act on another repo without changing directory. Found
# by the test, not by reading the regex.
GIT_WRITE='(^|[^[:alnum:]_-])git[[:space:]]+([^[:space:]]+[[:space:]]+)*(commit|push|add|rm|mv|checkout|switch|restore|reset|revert|merge|rebase|cherry-pick|apply|am|stash|clean|tag|branch|worktree|submodule|gc|prune|filter-branch|update-ref)([[:space:]]|$)'
REDIRECT='>[[:space:]]*[^|&]*'

block() {
  jq -nc --arg reason "$1" '{decision:"block", reason:$reason}'
  exit 0
}

MENTIONS_MESHLY=0
[[ "$SCRUBBED" =~ $MESHLY_PATH ]] && MENTIONS_MESHLY=1

# `cd` into a meshly tree followed by anything mutating: the path and the verb
# are in the same command but not adjacent, which is the shape that would slip
# past a naive "verb then path" match.
if [[ "$MENTIONS_MESHLY" -eq 1 ]]; then
  if [[ "$SCRUBBED" =~ $GIT_WRITE ]]; then
    block "BLOCKED: a git WRITE targeting a meshly repository, from a session working in the public fork.

The meshly repos are private and have their own gates, approvers and hooks. A change made from here arrives with none of them applied.

Hand it over instead:
  just export-handoff        # sanitized prompt for a meshly agent to run in its own repo

Reads are fine — git status/log/diff/show/ls-tree against a meshly path are not blocked.

Override with MESHLY_WRITE_INTENDED=1 if you can say why."
  fi
  if [[ "$SCRUBBED" =~ $WRITE_VERB ]]; then
    block "BLOCKED: a filesystem WRITE targeting a meshly repository, from a session working in the public fork.

Work in the fork happens here; anything the meshly side needs is handed over as a prompt a meshly agent runs under its own hooks:
  just export-handoff

Reads are fine. Override with MESHLY_WRITE_INTENDED=1 if you can say why."
  fi
  if [[ "$SCRUBBED" =~ $REDIRECT ]] && [[ "$SCRUBBED" =~ (/home/jw/dev/meshly|~/dev/meshly)[^[:space:]]*[[:space:]]*$ ]]; then
    block "BLOCKED: output redirected into a meshly repository path.

A redirect is a write even when the command before it is a read. Use \`just export-handoff\` to hand the work over instead.

Override with MESHLY_WRITE_INTENDED=1 if you can say why."
  fi
fi

echo '{"decision":"approve"}'

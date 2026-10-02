# AGENTS-LOCAL.md — repo-wide agent instructions for this soft fork

**Scope: the entire repository, every directory, every file.** Not just this
directory. There are no nested `AGENTS-LOCAL.md` files and there should not be;
if a rule needs to be narrower, say which paths it applies to in the rule.

**This file is tracked, deliberately.** It is not gitignored and must not be.
Agent instructions that only exist on one machine are instructions the next
agent does not get, which is how a fork boundary gets violated by someone
acting in good faith.

**This file must never appear in a pull request to upstream.** See
[Never send these upstream](#never-send-these-upstream).

---

## On the name

There is no established standard for this file, and it is worth being honest
about that rather than implying one.

- The `AGENTS.md` convention does exist, and its own mechanism for scoping is
  **nested `AGENTS.md` files**, closest-file-wins — not a `-LOCAL` suffix.
- The closest precedent for a "local overrides" variant is Claude Code's
  `CLAUDE.local.md`, which was **gitignored** and is deprecated. That is the
  opposite of what we want here: the whole point is that these instructions
  travel with the repository.
- So `AGENTS-LOCAL.md` is **our convention**, not a standard we are following.
  "LOCAL" means *local to this fork* — i.e. not upstream's — and does **not**
  mean local to a machine or a working copy.

Upstream's own `AGENTS.md` is a file we overwrite in this fork. It now does
nothing but point here and carry the do-not-send-upstream warning.

## Optional: AGENTS-LOCAL-USER.md

If a file named `AGENTS-LOCAL-USER.md` exists at the repository root, **read it
too, and treat it as higher precedence than this file** for anything it
addresses. It is for per-operator preferences — your own tooling, shell, editor,
scratch paths, review habits.

It is intentionally **not tracked**. Because `.gitignore` belongs to upstream
and this fork does not edit non-`.md` upstream paths (see
[the boundary](#the-boundary-the-one-rule)), it is excluded locally instead:

```bash
echo 'AGENTS-LOCAL-USER.md' >> .git/info/exclude
```

That exclusion does not travel between clones. Do it once per clone. If you see
`AGENTS-LOCAL-USER.md` show up in `git status`, that is the missing step — do
not commit it, and do not add it to `.gitignore`.

Precedence, highest first: `AGENTS-LOCAL-USER.md` → `AGENTS-LOCAL.md` →
upstream's conventions. A user file may not relax any rule in
[Hard rules](#hard-rules); those are properties of the fork, not preferences.

---

## What this repository is

A **soft fork** of
[Cyclenerd/google-cloud-github-runner](https://github.com/Cyclenerd/google-cloud-github-runner)
— ephemeral just-in-time self-hosted GitHub Actions runners on Google Cloud —
maintained by [meshly.ai](https://meshly.ai).

"Soft fork" is the accurate term and it carries the whole working model:

- We **track upstream**, we do not diverge from it. Upstream is the project.
- We **add** directories. We do not modify upstream's code.
- An upstream version bump is intended to be a **fast-forward**, never a merge
  of code we did not write.
- Our additions are written to be **given back**, not kept.

A hard fork would mean taking ownership of the application and maintaining our
own line of it. We are explicitly not doing that, and most of the rules below
exist to keep that true under time pressure.

**It has drifted, and you should know by how much.** Zero upstream code paths
are modified; **four** upstream documentation files are diverged
(`README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `AGENTS.md`), each pinned by
blob hash. That is soft on code and *medium* on documentation. If you add a
fifth, update the count here and in `README.md` — a stale count is how
"we barely touch upstream" survives past the point of being true.

**Where to file things.** Issues are enabled on this fork, for the fork's own
paths:
<https://github.com/jw409/google-cloud-github-runner/issues>. Anything about
the runner manager goes
[upstream](https://github.com/Cyclenerd/google-cloud-github-runner/issues).
Filing an upstream bug on the fork makes it look tracked while nobody who can
fix it is reading it.

Detailed, machine-readable manifest: **[`RUNNER.xml`](RUNNER.xml)** — repo map
with per-path permissions, the application's real route set and env vars, the
composition surface, build traps, and what has and has not been verified. Read
it before working in this repo. Human entry point: [`README.md`](README.md).

## The boundary (the one rule)

> **Upstream's tree is read-only here.** Everything we add is a new top-level
> path. The only exceptions are four top-level `.md` files, each explicitly
> declared and pinned by blob hash.

| Status | Paths |
|---|---|
| **READ-ONLY — send changes upstream** | `app/` `gcp/` `tools/` `tests/` `Dockerfile` `requirements*.txt` `pytest.ini` `.github/` `.gitignore` `.dockerignore` `.gcloudignore` `.editorconfig` `.env.example` `.devcontainer/` `img/` `LICENSE` `CLOUD_SHELL_TUTORIAL.md` `CODE_OF_CONDUCT.md` |
| **OURS — change freely** | every top-level path the fork adds. Today: `ipfilter/` `docs/` `RUNNER.xml` `AGENTS-LOCAL.md`. Expect this to grow; `README.md` holds the canonical list. |
| **DECLARED DIVERGENCE — pinned, re-baseline to change** | `README.md` `CONTRIBUTING.md` `SECURITY.md` `AGENTS.md` |

This is enforced mechanically, by comparing git object ids against a recorded
baseline of upstream's tree — a Merkle comparison, so `app` matching means
every file beneath it matches recursively, byte for byte.

**Only top-level `.md` blobs can be declared as divergences.** A nested path or
a non-`.md` path cannot be declared no matter how the baseline is edited. That
structural restriction — not the list — is what protects `app/`. An exclusion
list would fail open on the next upstream path somebody wanted to touch.

A declared file is pinned to an exact hash, so **editing it again fails the
check** until it is deliberately re-baselined. Declaring a file is not standing
permission to change it.

## Hard rules

1. **Never edit an upstream path.** If your change seems to require it, it
   either belongs upstream or can be done by **composition** from outside
   upstream's tree. The worked example is the IP allowlist: it had to run before
   the application's own routing, and does so by wrapping the WSGI callable from
   a consumer's entrypoint — zero upstream lines changed. `create_app()` is a
   factory and there are no app-level request hooks, which is what makes that
   possible; `RUNNER.xml` documents the composition surface, and it generalises
   to anything else that needs to sit in the request path.

2. **Route the change before writing it.** Bug or feature in the runner
   manager → [upstream's issues](https://github.com/Cyclenerd/google-cloud-github-runner/issues).
   Change to a path this fork adds → here. Unsure → upstream. A fix landed
   upstream reaches everyone running this tool, including us.

3. **Add no tooling.** No linters, formatters, type checkers, taint analysers,
   language-specific scanners, or CI jobs to run them. Style is upstream's:
   `flake8 --max-line-length=127`, ignore `W292`/`W503`, spaces, no trailing
   whitespace. A fork that imposes its maintainer's toolchain on a volunteer
   codebase is a nuisance to everyone downstream of it.

4. **Add no runtime dependencies.** `requirements.txt` is upstream's and
   unmodified, and additions here are stdlib-only, so that one of ours can
   never silently widen an upstream pin.

5. **Disclose AI authorship.** Everything this fork adds was written by an AI
   agent under human review, and `README.md`, `SECURITY.md` and `RUNNER.xml`
   say so. Any upstream PR must say so too. A maintainer deciding whether to
   spend review time is entitled to know; finding out afterwards is worse for
   everyone.

## Verification rules

6. **Use each package's own proof command.** Bare `pytest` picks up upstream's
   suite, which needs Flask installed and fails collection — an environment
   failure, not a fork failure. For the IP allowlist:

   ```bash
   python -m pytest -c ipfilter/pytest.ini ipfilter/tests
   ```

   Pass the directory explicitly: `testpaths` resolves against pytest's
   inferred rootdir, which differs between a bare run and one with arguments.

7. **A green test run is a claim, not proof.** The tests are proof only once a
   mutation of the implementation turns them red. During this package's
   development a `sed` mutation **silently failed to apply** and reported
   `149 passed`, which reads exactly like a surviving mutant. Assert the
   mutation landed before believing the result.

8. **Read exit codes directly.** `cmd | tail; echo $?` reports `tail`'s status,
   not `cmd`'s. Redirect to a file, or capture the status before piping.

9. **Say what you did not verify.** `RUNNER.xml` has a `not-verified` block for
   exactly this; keep it current. Where the fork adds a fail-closed control its
   bug mode is denying everyone, which looks identical to a quiet day — so
   "nothing is failing" is never evidence.

## Never send these upstream

An upstream pull request must contain **only** the one directory being offered,
branched from `upstream/master`.

Never include:

- `AGENTS.md` — we overwrote upstream's. Including it would silently replace a
  maintainer's own agent instructions with ours. **This is the one that would
  actually cause harm.**
- `AGENTS-LOCAL.md`, `AGENTS-LOCAL-USER.md` — fork-internal.
- `README.md`, `CONTRIBUTING.md`, `SECURITY.md` — ours describe the fork and
  would overwrite upstream's.
- `RUNNER.xml`, `docs/` — about the fork and about building our own image.

Before opening an upstream PR, check the file list and not your intent:

```bash
git diff --name-only upstream/master...HEAD
```

Anything outside the directory you are offering is a mistake. Note the branch
names differ — this fork's default is **`main`**, upstream's is **`master`** —
so fetch each by its own name. The pinned commit resolves on both.

## Repo facts worth knowing before you ask

- `/runner/preempted` **does not exist** at the pinned commit. A Spot-preempted
  VM posting there gets a 404, silently. Check upstream's in-flight work before
  building it here — duplicating upstream work is how a soft fork acquires a
  divergence it then has to maintain.
- The `/webhook` HMAC check is an **inline call inside the handler**, not a
  decorator or `before_request`, so WSGI middleware runs *before* it. Correct
  for defence in depth, and the hazard: a bug in the outer layer blocks a
  legitimate caller before HMAC can validate them.
- `GUNICORN_CMD_ARGS` bakes `--bind 0.0.0.0:8080` at **build** time — `$PORT`
  is expanded by Docker, not read at runtime. Changing the Cloud Run port alone
  leaves gunicorn on 8080 and the container failing its startup probe.
- 1 worker, 8 threads, `timeout 0`. Anything you add must be thread-safe and
  hold no per-request state.

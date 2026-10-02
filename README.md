# google-cloud-github-runner — meshly.ai fork

[![Badge: License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Badge: Python](https://img.shields.io/badge/Python-3670A0?logo=python&logoColor=ffdd54)](#readme)
[![Badge: Google Cloud](https://img.shields.io/badge/Google%20Cloud-%234285F4.svg?logo=google-cloud&logoColor=white)](#readme)

A **soft fork** of **[Cyclenerd/google-cloud-github-runner](https://github.com/Cyclenerd/google-cloud-github-runner)** —
ephemeral, just-in-time self-hosted GitHub Actions runners on Google Cloud.

*Soft fork* is the accurate term and it carries the working model: we **track**
upstream rather than diverge from it, we **add** directories rather than modify
upstream's code, an upstream bump is meant to be a **fast-forward**, and our
additions are written to be **given back**. We are explicitly not taking
ownership of our own line of the application.

**Read upstream's documentation, not this file.** Everything about what the
tool is, how to deploy it, how to configure it, its architecture, its
environment variables and its API lives in
**[upstream's README](https://github.com/Cyclenerd/google-cloud-github-runner#readme)**
and is not duplicated here. Duplicated docs rot, and a fork's copy rots
fastest, so this README covers one thing only: **how this fork differs from
upstream.** If you are evaluating the tool, you are in the wrong repository —
go upstream.

## ⚠️ AI-generated code disclosure

**Everything this fork adds was written by an AI coding agent** (Claude), under
human direction and review. That covers every path this fork
adds, and the fork-facing documentation including this README. Treat it accordingly:

* **Upstream's code is not affected.** The fork modifies no path upstream owns,
  so nothing generated here has touched the application. That is verified
  mechanically, not asserted — see
  [the invariant](#the-additions-never-edits-invariant).
* **Agents: read [`AGENTS-LOCAL.md`](AGENTS-LOCAL.md) before editing anything
  here.** It is repo-wide and states the read-only boundary, how to route a
  change, and what must never be included in an upstream pull request.
* **Review it before you trust it.** Some of it is access-control code, which
  is exactly the category where plausible-looking wrong code is most expensive:
  a bug does not misbehave, it denies every caller, and that looks
  indistinguishable from a quiet day. Read the tests — they are the claim — and
  do not deploy any of it on our say-so.
* **What was actually verified**, so you can judge the rest: the test suite
  passes, it is `flake8`-clean under upstream's own rules, and twelve
  deliberate mutations of the implementation each turn the suite red (wrong
  address family, ignored chain index, unevaluable treated as allow, uncovered
  route allowed, and so on). That establishes the tests detect those specific
  failures. It does not establish the design is right for your deployment.
* **If we offer any of this upstream**, it will say the same thing in the pull
  request. A maintainer deciding whether to review a patch is entitled to know
  how it was produced, and finding out afterwards is worse for everyone.

No claim is made here that a human hand-wrote it. We would rather say so plainly
than have you infer it from the commit style.

## What's different from upstream

No upstream **code** is changed. Two directories are added, two root files are
added, and four documentation files are diverged — see
[how soft this fork is](#how-soft-is-this-fork-honestly) for the honest
accounting.

| | Change | Path |
|---|---|---|
| ➕ | **IP allowlist** — a policy core plus WSGI and ASGI adapters, stdlib-only, framework-free, no address ranges baked in. Not wired into the application. | [`ipfilter/`](ipfilter/) |
| ➕ | **Self-hosting notes** — Artifact Registry layout and Cloud Build caching for running your own build of the manager image. | [`docs/`](docs/) |
| ➕ | **Agent instructions** — repo-wide rules for AI agents working here, plus a machine-readable manifest. | [`AGENTS-LOCAL.md`](AGENTS-LOCAL.md), [`RUNNER.xml`](RUNNER.xml) |
| ✏️ | This file, [`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md) and [`AGENTS.md`](AGENTS.md), to say what the fork is and where to send patches. | — |
| ✏️ | Default branch is `main`. Upstream's is `master`. | — |

That is the complete list, and it is mechanically enforced rather than
promised — see [below](#the-additions-never-edits-invariant).

**Not changed:** `app/`, `gcp/`, `tools/`, `tests/`, `Dockerfile`,
`requirements.txt`, `.github/`, and every other path upstream owns. Byte for
byte. No patch series, no cherry-picks, no behaviour changes, no new runtime
dependencies. The application in this repository does exactly what upstream's
does, and `ipfilter/` is **not wired into it** — enabling it is a composition
step a deployment performs for itself, which is why `app/` does not need to
move.

## How soft is this fork, honestly

"Soft fork" is a gradient, not a badge, and this one has drifted along it. Where
it actually sits today:

| | Count | What |
|---|---|---|
| Upstream **code** paths modified | **0** | `app/` `gcp/` `tools/` `tests/` `Dockerfile` `requirements*.txt` `.github/` — byte-identical, mechanically verified |
| Upstream **doc** paths diverged | **4** | `README.md` `CONTRIBUTING.md` `SECURITY.md` `AGENTS.md` — each pinned by blob hash |
| Directories added | **2** | `ipfilter/` `docs/` |
| Root files added | **2** | `AGENTS-LOCAL.md` `RUNNER.xml` |

So: **soft on code, medium on documentation.** Four diverged doc files is more
than "a fork notice", and pretending otherwise would be the kind of claim that
gets believed and then relied on. The thing that keeps it soft is that the
divergence is confined to files that cannot change program behaviour — and that
this is enforced structurally, not by good intentions: only top-level `.md`
blobs can be declared, so no amount of editing the baseline can add `app/` or
`requirements.txt` to that list.

**What would make it a hard fork** — stated so we notice if it happens:

1. Any modification to an upstream **code** path. The mechanism makes this
   impossible to do quietly; it would be a deliberate choice.
2. Carrying a **patch series** against upstream, or a merge of upstream changes
   we rewrote. A bump stops being a fast-forward.
3. Our additions acquiring **dependencies** upstream does not have.
4. Any addition becoming **load-bearing for the application** rather than
   something a deployment composes in.
5. Offering nothing upstream. A soft fork that never sends anything back is
   just a slow hard fork.

If you are reading this because one of those happened, the README is the thing
that should have been updated first.

## Why the fork exists

We needed somewhere to put code upstream does not have yet, without editing
upstream's code to do it.

The reason for the constraint is selfish: it keeps a version bump a
fast-forward instead of a merge of code we did not write. What it specifically
buys is protection from a patch that applies **with fuzz** — which succeeds,
and now means something different, and nothing fails and nobody looks.

It also means you can audit this fork without reading a diff. We changed
nothing; we added directories.

### The additions-never-edits invariant

> Every path upstream owns is byte-identical here, **except** an explicitly
> baselined set of top-level `.md` files, each pinned by its exact blob hash.
> Everything this fork adds is a new top-level path.

Checked by comparing git object ids against a recorded baseline of upstream's
tree, which is a Merkle comparison — `app` matching means every file beneath
it matches, recursively. The four documentation exceptions are declared
individually and pinned, so editing one *again* fails the check until it is
re-baselined, and a non-`.md` or nested path cannot be declared at all. That
last restriction is the one that actually protects `app/`.

## The added packages

Each addition is self-contained, vendor-neutral, and built to be given away:
named for what it does rather than for us, no dependency on our deployment, and
no import of this application — so the offer upstream is "add exactly this
directory". None of them is wired into the runner manager; enabling one is a
composition step a deployment performs for itself, which is why upstream's
`app/` never has to move.

Each carries its own design notes and its own proof command in its directory.
For the IP allowlist that is [`ipfilter/__init__.py`](ipfilter/__init__.py) and:

```bash
python -m pytest -c ipfilter/pytest.ini ipfilter/tests
```

Pass the directory explicitly — `testpaths` resolves against pytest's inferred
rootdir, which differs between a bare run and one with arguments, and a bare
run picks up the project's own suite instead.

## Contributing

**Upstream first** — <https://github.com/Cyclenerd/google-cloud-github-runner/issues>.
For this fork's own paths, its tracker is open:
<https://github.com/Meshly-Open-Source/google-cloud-github-runner/issues>.
A fix landed upstream reaches everyone running this tool, including us; a fix
landed here strands you on a fork. We will not merge a change that should have
gone upstream.

Changes to the paths this fork adds are welcome here, since they have nowhere
upstream to go yet. See [CONTRIBUTING.md](CONTRIBUTING.md) for how we evaluate
them, including the priority order, stated plainly.

## Licence and credit

Upstream is the work of **[Cyclenerd](https://github.com/Cyclenerd)** and its
contributors, used here under the [Apache-2.0 licence](LICENSE). Additions in
this fork are under the same licence.

If this project is useful to you, support **upstream**, not this fork.

## Sponsor

Maintained and sponsored by **[meshly.ai](https://meshly.ai)**, who run their
CI fleet on it.

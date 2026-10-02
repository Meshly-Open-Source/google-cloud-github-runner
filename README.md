# google-cloud-github-runner — meshly.ai fork

[![Badge: License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Badge: Python](https://img.shields.io/badge/Python-3670A0?logo=python&logoColor=ffdd54)](#readme)
[![Badge: Google Cloud](https://img.shields.io/badge/Google%20Cloud-%234285F4.svg?logo=google-cloud&logoColor=white)](#readme)

A fork of **[Cyclenerd/google-cloud-github-runner](https://github.com/Cyclenerd/google-cloud-github-runner)** —
ephemeral, just-in-time self-hosted GitHub Actions runners on Google Cloud.

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
human direction and review. That covers all of `ipfilter/`, all of `docs/`, and
this README, `CONTRIBUTING.md` and `SECURITY.md`. Treat it accordingly:

* **Upstream's code is not affected.** The fork modifies no path upstream owns,
  so nothing generated here has touched the application. That is verified
  mechanically, not asserted — see
  [the invariant](#the-additions-never-edits-invariant).
* **Review it before you trust it.** `ipfilter/` is a fail-closed access
  control, which is exactly the category where plausible-looking wrong code is
  most expensive: a bug does not misbehave, it denies every caller, and that
  looks indistinguishable from a quiet day. Read the tests — they are the
  claim — and do not deploy it on our say-so.
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

Nothing is changed. Two directories are added.

| | Change | Path |
|---|---|---|
| ➕ | **Framework-agnostic IP allowlist** — a pure policy core plus WSGI and ASGI adapters. Stdlib only, no web framework in the core, and no address ranges anywhere in the package. | [`ipfilter/`](ipfilter/) |
| ➕ | **Self-hosting notes** — Artifact Registry layout and Cloud Build caching for running your own build of the manager image. | [`docs/`](docs/) |
| ✏️ | This file, [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`SECURITY.md`](SECURITY.md), to say what the fork is and where to send patches. | — |
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
it matches, recursively. The three documentation exceptions are declared
individually and pinned, so editing one *again* fails the check until it is
re-baselined, and a non-`.md` or nested path cannot be declared at all. That
last restriction is the one that actually protects `app/`.

## `ipfilter/`

Built to be given away. It is named for what it does rather than for us, takes
no dependency on this application, and imports no web framework, so the offer
to upstream is "add exactly this directory" — no renames, no imports to
unpick.

Three deliberate properties, each of which is a mistake we wanted to make
impossible:

* **No address ranges in the package.** A library that ships a default range
  set turns one consumer's allowlist into a silent default for every future
  consumer. The consumer supplies named sets; a policy naming a set the
  consumer did not supply is *unevaluable*, and under fail-closed that denies.
* **Three decisions, not two** — allow, deny, **unevaluable**. "This caller is
  not on the list" and "I do not have a list" have opposite implications and
  different fixes, and a single `denied` counter conflates them. The collapse
  to a block happens at the enforcement edge, as a configured fail mode, with
  the reason preserved in the record.
* **Every route explicit, including "no check".** A table that covers the
  routes it knows about and lets the rest through is an inclusion list, and it
  fails open on the route added next week by someone who never read it. An
  uncovered route is a **startup failure**; a route that genuinely takes no
  address check is declared as such and must carry a written justification.

Design notes are in [`ipfilter/__init__.py`](ipfilter/__init__.py). What is
actually guaranteed is in [`ipfilter/tests/`](ipfilter/tests/):

```bash
python -m pytest -c ipfilter/pytest.ini ipfilter/tests
```

Pass the directory explicitly — `testpaths` resolves against pytest's inferred
rootdir, which differs between a bare run and one with arguments, and a bare
run picks up the project's own suite instead.

## Contributing

**Upstream first** — <https://github.com/Cyclenerd/google-cloud-github-runner/issues>.
A fix landed upstream reaches everyone running this tool, including us; a fix
landed here strands you on a fork. We will not merge a change that should have
gone upstream.

Changes to `ipfilter/` or `docs/` are welcome here, since they have nowhere
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

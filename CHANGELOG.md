# Changelog — meshly.ai fork

What is **uniquely ours**, relative to
[Cyclenerd/google-cloud-github-runner](https://github.com/Cyclenerd/google-cloud-github-runner).

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning is of **the fork's own additions**, not of upstream — upstream is
tracked by commit and its releases are its own.

**Why this file exists separately from the README's diff table:** that table
says which paths exist. This says what *changed* and what the consequence is,
and it separates two things the table runs together — additions at the
**source** layer, which cost an adopter nothing, from differences in the
**artefact** we actually deploy, which change behaviour. The second list is
the one that matters and the README overclaimed on it until 2026-10-03.

Entries describe consequences, not commits. This is read by someone deciding
whether to adopt or upgrade.

---

## [Unreleased]

### The artefact differs from upstream's — read this first

Not a list of files; a list of behaviour changes in what runs.

| | upstream | this fork |
|---|---|---|
| Entrypoint | `gunicorn run:app` | `gunicorn meshly.wsgi:app`, a module of ours |
| Request path | straight into Flask routing | a WSGI wrapper can be installed that runs **before** the app's own in-handler signature check |
| `README` / `CONTRIBUTING` / `SECURITY` / `AGENTS` | upstream's | ours |
| Community health files | upstream's | ours; issue templates replaced, `FUNDING.yml` **removed** |

So: a **soft fork at the source layer, a derivative product at the artefact
layer.** No file upstream owns is edited except four documentation files, each
pinned by hash — but the thing we deploy is not upstream's application with a
different name on the box.

**Not covered by upstream's tests.** Upstream's CI lints and tests `app/`.
Nothing tests the composed artefact. That gap is ours, not theirs.

### Added

- **`ipfilter/`** — a framework-agnostic IP allowlist: a pure policy core plus
  WSGI and ASGI adapters. Stdlib only, no framework import anywhere, and **no
  address ranges in the package** (a library-level default range set would
  make one consumer's allowlist a silent default for every future consumer).

  Consequences for anyone enabling it:
  - It returns **three** decisions, not two — allow, deny, and *unevaluable*.
    "You are not on the list" and "we have no list" have opposite implications
    and different owners; the collapse to a block happens at the enforcement
    edge as a configured fail mode, with the reason preserved.
  - **`chain_index` is required and has no default.** A default is correct for
    exactly one proxy topology and silently wrong for the rest, and silently
    wrong here denies every caller. You must measure your forwarded-header
    chain before enforcing. An out-of-range index reports
    `chain-shorter-than-index` rather than falling back, because a fallback
    hides exactly that misconfiguration.
  - **Every route needs an explicit entry, including "no check".** An
    uncovered route is a **startup failure**, asserted against the route set
    read from the running application rather than a grep. A route that
    genuinely takes no address check must carry a written justification.
  - It is **not wired into the application.** Enabling it is a composition
    step a deployment performs for itself, which is why `app/` does not move.
  - Deploy `log_only` first. A fail-closed filter fails *quietly*: when it
    rejects everything there is no error and no failed request, and the symptom
    is indistinguishable from a quiet afternoon.

  149 tests; 12 deliberate mutations of the implementation each turn the suite
  red. Design notes in `ipfilter/__init__.py`.

- **`docs/`** — operating notes for building your own manager image: Artifact
  Registry layout and Cloud Build caching. Includes the trap that a cleanup
  policy deleting untagged images will delete the digest production is pinned
  to, failing at the next cold start with no deploy having happened.

- **`docs/CI-HARDENING.md`** — what supply-chain hardening to adopt, tiered by
  cost, derived from reading two reference repositories' workflow files.

- **`CLAUDE.md`, `AGENTS-LOCAL.md`, `RUNNER.xml`** — agent instructions. The
  entry point says to *read and evaluate* upstream's `AGENTS.md` rather than
  obey it: it is accurate about the application and was written for a
  repository where the tree is writable, so following it here would break the
  invariant this fork exists to hold.

- **`justfile`** — `check` / `test` / `lint` / `boundary` / `test-hooks`.
  `boundary` exits **2** when it cannot compare rather than printing clean.

- **`.github/ATTRIBUTION.md`** — third-party material with its licence, its
  copyright, and an explicit list of what we changed.

### Changed

- **Default branch is `main`.** Upstream's is `master`. Anything fetching by
  branch name needs the right one per remote; the pinned commit resolves on
  both.
- **Issue templates replaced** with seven adapted from
  [Josee9988/project-template](https://github.com/Josee9988/project-template)
  (MIT, credited). Upstream's bug report asked for environment facts that do
  not describe this system; these ask for deployment, Python version, commit,
  region/zone, machine type and provisioning model, the `runs-on` label, and a
  log entry.
- **`blank_issues_enabled: true`**, reversing upstream. A reporter who fits no
  template needs a way to say so rather than being forced into the wrong one.
- **Contact links and security reporting rerouted.** Upstream's config sent
  reporters to the upstream author's personal Mastodon, and its
  `PULL_REQUEST_TEMPLATE` asked contributors to confirm they had read
  upstream's `CONTRIBUTING`. Both are wrong on a fork.
- **`SECURITY.md` routes reports by which code owns them**, since upstream's
  named a maintainer who does not own this fork.

### Removed

- **`FUNDING.yml`.** It put a Sponsor button on our repository pointing at
  upstream's author. Supporting upstream is right — the README says so — but a
  funding button is a solicitation and ours should not solicit on someone
  else's behalf without them choosing it.

### Not changed, deliberately

`app/`, `gcp/`, `tools/`, `tests/`, `Dockerfile`, `requirements.txt`,
`.github/workflows/`. Byte for byte, verified by git-object comparison against
a recorded baseline rather than asserted. No patch series, no cherry-picks, no
new runtime dependencies.

### Known gaps

- **`chain_index` is unmeasured.** Cloud Run request logs carry no header map
  at all, so it cannot be derived from existing logs. Until measured per
  ingress path, `ipfilter` should run `log_only` only.
- **No CI on the fork's own code.** Upstream's workflow lints `app/` and
  `tests/`; nothing runs `ipfilter`'s suite on a push.
- **`/runner/preempted` does not exist.** A Spot-preempted VM posting there
  gets a 404, silently.
- **Nothing tests the composed artefact**, only upstream's `app/` tree.

---

## Upstream tracking

Pinned by commit, never by branch, and bumps are fast-forwards rather than
merges. Two upstream pull requests are archived in this fork as
`archive/pr95` and `archive/pr96` — a pull-request ref is not durable storage
and can be force-pushed away.

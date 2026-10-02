<!-- Adapted from Josee9988/project-template (MIT) — see .github/ATTRIBUTION.md -->

## ⚠️ Is this change in the right repository?

**This repository is a [soft fork](../README.md#how-soft-is-this-fork-honestly).**
Only the paths listed in [`README.md`](../README.md) are ours. Everything else —
`app/`, `gcp/`, `tools/`, `tests/`, the `Dockerfile`, `requirements.txt`,
`.github/workflows/` — belongs to
[upstream](https://github.com/Cyclenerd/google-cloud-github-runner), and a PR
touching those **will be closed with a pointer there**, because a fix landed
upstream reaches everyone running this tool and a fix landed here strands you on
a fork.

If you are not sure, open it upstream. Being redirected costs one round trip;
maintaining a divergence costs forever.

---

## What does this change, and why?

<!-- The outcome first: what is different for a user or an operator afterwards,
     and what problem that solves. Not a list of files. -->

*

## How did you verify it?

<!-- Commands you actually ran and what they printed. A claim that something
     passes is not the same as having watched it pass.

     If you touched a package here, run ITS proof command — each one is named in
     its directory. For the IP allowlist:
         python -m pytest -c ipfilter/pytest.ini ipfilter/tests

     Style is upstream's: flake8 --max-line-length=127 --extend-ignore=W292,W503 -->

*

## Checklist

<!-- Tick only what you actually did. An unticked box is fine and more useful
     than a ticked one that is aspirational. -->

- [ ] This change is confined to the paths this fork owns
- [ ] I read [CONTRIBUTING.md](../CONTRIBUTING.md)
- [ ] Tests cover the change, and I saw them fail before they passed
- [ ] No new runtime dependency (or the description argues for the one it adds)
- [ ] No new linter, formatter, scanner or CI job
- [ ] If any of this was AI-generated, the description says so

## Anything else

<!-- Risk, rollback, follow-ups, things you could not verify. "I could not test
     X" is a useful sentence, not an admission. -->

*

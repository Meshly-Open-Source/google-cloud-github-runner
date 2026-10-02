# Contributing

Thanks for looking. Two things to know before you spend any effort.

## 1. Go upstream first 🍴

This repository is a fork. The project is
**[Cyclenerd/google-cloud-github-runner](https://github.com/Cyclenerd/google-cloud-github-runner)**,
and that is where contributions belong.

If you have a bug, a feature request, or a patch for the runner manager
itself, open it upstream:

* **Issues** → <https://github.com/Cyclenerd/google-cloud-github-runner/issues>
* **Pull requests** → <https://github.com/Cyclenerd/google-cloud-github-runner/pulls>
* **Coding style** → upstream's
  [CONTRIBUTING.md](https://github.com/Cyclenerd/google-cloud-github-runner/blob/master/CONTRIBUTING.md)
  is the authority. For anything under `app/`, `gcp/` or `tools/`, follow it,
  not this file.

This is not a brush-off. A fix landed upstream reaches everyone running this
tool, including us. A fix landed here reaches us and strands you on a fork.
Upstream is also active — there is real work in flight there at any given
time, some of it fixing things we ourselves reported — so an issue opened
upstream has a decent chance of already being someone's problem.

**We will not merge a change here that should have gone upstream.** If you send
us one, we will say so and point you there, which wastes a round trip for both
of us. The one case where sending it here is right: the change is to a
directory this fork adds (see below), and so has nowhere upstream to go yet.

## 2. If it really does belong here 📥

This fork adds exactly two top-level paths of its own:

| Path | Scope |
|---|---|
| `ipfilter/` | Framework-agnostic IP allowlist — policy core, WSGI and ASGI adapters |
| `docs/` | Operating notes for building and hosting your own manager image |

Changes to those are welcome here. Anything else is upstream's.

**Issues are enabled on this fork**, scoped to exactly those two paths:
<https://github.com/jw409/google-cloud-github-runner/issues>. Please label the
subject in the title (`ipfilter:` / `docs:`) so it is obvious at a glance that
it is not an upstream bug filed in the wrong place.

An issue about the runner manager itself will be closed with a pointer
upstream. That is not unfriendliness — leaving it open here would mean it looks
tracked while nobody who can fix it is reading it.

### How we evaluate a contribution

Stated plainly, because an unstated priority order is just a slower rejection.
In this order:

1. **Does it benefit [meshly.ai](https://meshly.ai)?** We maintain this fork to
   run our own CI, on our own time, and that is the budget it comes out of.
2. **Does it benefit the wider community?** A change that is good for everyone
   is better than one that is only good for us, and we would rather find the
   general version of your idea than the narrow one.

Being honest about the order does not mean the second criterion is decoration.
`ipfilter/` is built to be given away — vendor-neutral, no framework in the
core, no hardcoded address ranges, named for what it does rather than for us —
precisely so that it can be offered upstream as "add this directory". If your
change makes it *more* generally useful, that helps on both counts.

If the answer to (1) is no but (2) is a clear yes, the right home is upstream
or your own fork, and we will tell you that rather than leave a PR open.

### What we need from a change

* **A test that fails without it.** For `ipfilter/` especially: it is a
  fail-closed security control, so a bug in it does not misbehave, it denies
  everyone — which looks exactly like a quiet day and is therefore invisible.
  Run `python -m pytest -c ipfilter/pytest.ini ipfilter/tests`.
* **No new runtime dependencies**, unless the PR argues for the one it adds.
  `ipfilter/` is stdlib-only on purpose: it needs set membership, not
  longest-prefix matching, so a C-extension trie would add a supply-chain
  entry and a build step in exchange for nothing.
* **Match the surrounding style.** `flake8 --max-line-length=127`, spaces,
  no trailing whitespace — upstream's rules, which this fork follows.
* **Please do not add tooling.** No new linters, formatters, type checkers,
  taint analysers or language-specific scanners, and no CI jobs to run them.
  We run a fair amount of that machinery on our own code and deliberately keep
  it out of this repository: it is upstream's project, it has its own
  conventions, and a fork that imposes its employer's toolchain on a volunteer
  codebase is a nuisance to everyone downstream of it. A PR whose diff is
  mostly configuration for a tool nobody asked for will be declined.

### Security

Do not open a public issue for a vulnerability. See [SECURITY.md](SECURITY.md).
If it affects upstream's code rather than the directories listed above, report
it upstream.

## Licence

Upstream is [Apache-2.0](LICENSE) and so is everything added here.
Contributions are accepted under the same terms.

Thanks again. ❤️

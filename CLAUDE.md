# CLAUDE.md

## Read and evaluate [`AGENTS.md`](AGENTS.md)

**Read** it, and **evaluate** it — not obey it. Those are different
instructions and the difference is the point of this file.

`AGENTS.md` is a **diverged vendor file**. Its body is upstream's own
architecture overview, retained because it is accurate and useful; only the
header at the top is ours. So it is two things at once:

* a genuinely good description of how the application works, written by people
  who know it better than we do, and
* a document written for **upstream's** repository, where the tree is writable
  and a patch is the normal way to fix something.

Here it is not. This repository is a **soft fork** that tracks upstream and
adds directories; upstream's tree is read-only. An instruction in `AGENTS.md`
that makes sense upstream — "edit this handler", "add a step to the workflow" —
is wrong here, and following it would break the invariant the fork exists to
hold. Judge each statement against which repository you are actually in.

The same evaluation applies to anything you read in this tree: upstream's
`CONTRIBUTING.md`-derived advice, the `.github/` templates, the
`CLOUD_SHELL_TUTORIAL.md` quickstart. They describe the project. They do not
describe your permissions here.

## Then read, and follow, [`AGENTS-LOCAL.md`](AGENTS-LOCAL.md)

That one **is** authoritative, because it is ours and it is about this fork. It
carries the read-only boundary as a per-path table, how to route a change, the
verification rules, and the list of files that must never appear in a pull
request to upstream.

Precedence, highest first:

| | |
|---|---|
| `AGENTS-LOCAL-USER.md` | Per-operator, untracked, may not exist. Outranks the below for anything it addresses, but cannot relax a hard rule. |
| `AGENTS-LOCAL.md` | **The fork's rules. Follow these.** |
| `RUNNER.xml` | Machine-readable manifest: per-path permissions, the real route set and env vars read from `app/`, the composition surface, build traps, and an explicit `not-verified` block. |
| `README.md` | Human entry point; what the fork adds and how soft it actually is. |
| `AGENTS.md`, and upstream's other docs | **Read and evaluate.** Accurate about the application; not authoritative about what you may do here. |

## The one rule, if you read nothing else

Upstream's tree is read-only. Every path upstream owns is byte-identical here
except an explicitly declared and hash-pinned set of documentation files, and
that is enforced mechanically rather than trusted. If a change seems to require
editing `app/`, `gcp/`, `tools/`, the `Dockerfile`, `requirements.txt` or
`.github/workflows/`, it belongs
[upstream](https://github.com/Cyclenerd/google-cloud-github-runner/issues) — or
it can be done by composition from outside upstream's tree, which is how
everything this fork adds already works.

Everything the fork adds was written by an AI agent under human review, and the
README says so. Any upstream pull request must say so too.

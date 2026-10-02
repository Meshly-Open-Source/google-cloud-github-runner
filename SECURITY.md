# Security Policy

This is the **meshly.ai fork** of
[Cyclenerd/google-cloud-github-runner](https://github.com/Cyclenerd/google-cloud-github-runner).
Which repository a vulnerability belongs to depends on which code it is in, so
please check before reporting — it decides who can actually fix it.

**Do not open a public issue for a vulnerability, in either repository.**

## If it is in upstream's code

That is `app/`, `gcp/`, `tools/`, `Dockerfile`, `requirements.txt`, `.github/`
— every path except the two listed below. This fork does not modify any of
them, byte for byte, so a vulnerability there is upstream's and affects
everyone running the tool, not just us.

Report it to upstream, following
**[upstream's security policy](https://github.com/Cyclenerd/google-cloud-github-runner/blob/master/SECURITY.md)**.

We would appreciate a heads-up at `security@meshly.ai` so we can assess our own
exposure, but please report upstream first and do not let us hold you up — the
fix has to land there.

## If it is in this fork's own code

Only two paths are ours:

| Path | What it is |
|---|---|
| `ipfilter/` | Framework-agnostic IP allowlist — policy core, WSGI and ASGI adapters |
| `docs/` | Operating notes |

Report those privately to **`security@meshly.ai`**, or via
[GitHub private vulnerability reporting](https://github.com/jw409/google-cloud-github-runner/security/advisories/new)
on this repository.

Please include the version or commit, what an attacker gains, and a
reproduction if you have one.

### Especially wanted in `ipfilter/`

It is a fail-closed access control, and its failure mode is quiet, so the two
bug classes we most want to hear about are:

1. **A bypass** — any input that yields `allow` for an address no configured
   set contains. Forwarded-header shapes are the obvious surface: injected
   chain prefixes, bracketed or port-suffixed addresses, mixed address
   families, duplicated headers, encodings we did not consider.
2. **A silent total denial** — any input or configuration that makes it deny
   every caller without that being evident. This matters as much as a bypass
   and is reported far less, because "nothing is being accepted" is
   indistinguishable from "nobody is calling us". If you find a way to make it
   fail shut and look healthy, that is a real finding and we want it.

A disagreement between the WSGI and ASGI adapters on the same request is also
a finding, whichever way it falls.

## What you get

Our genuine thanks, credit in the fix commit if you want it, and a straight
answer about whether and when it is fixed. We do not run a bug bounty and have
no money to offer.

## Scope

This policy covers the source in this repository. It does not cover meshly.ai's
production systems or any deployment of this tool other than our own — for
anything about meshly.ai's services, use `security@meshly.ai`.

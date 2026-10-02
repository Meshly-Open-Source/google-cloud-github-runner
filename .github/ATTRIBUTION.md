# Attribution for third-party material in this fork

## Issue and pull-request templates

The files in `.github/ISSUE_TEMPLATE/` and `.github/PULL_REQUEST_TEMPLATE.md`
are adapted from **[Josee9988/project-template](https://github.com/Josee9988/project-template)**,
used under the MIT licence. They are good templates and there was no reason to
write worse ones from scratch.

**What we changed**, so the differences are not mistaken for the original's
work:

* Author assignment removed (`assignees: Josee9988` → empty) — this fork has no
  single owner to route to, and a non-collaborator assignee is silently dropped
  anyway.
* The environment section of the bug report replaced: the original asks for Node
  and npm versions and a browser, which tell you nothing about a Python service
  on Cloud Run that creates GCE VMs. It now asks for deployment, Python version,
  repository commit, region/zone, machine type and provisioning model, the
  `runs-on` label, and a log entry.
* Contact links rerouted. The original points at its author's personal email;
  upstream's pointed at upstream's author's Mastodon. Both now point upstream
  for anything about the software, and at this fork's private reporting form for
  the paths the fork adds.
* `CODE_OF_CONDUCT.md` path corrected — upstream keeps it at the repository
  root, not under `.github/`.
* `FUNDING.yml` and the legacy single-file `ISSUE_TEMPLATE.md` were **not**
  taken from the template, and upstream's `FUNDING.yml` was removed.

The original's licence, reproduced in full as MIT requires:

```
MIT License

Copyright (c) 2020 Jose Gracia Berenguer

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NON INFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## The application itself

Everything outside the paths listed in `README.md` is
**[Cyclenerd/google-cloud-github-runner](https://github.com/Cyclenerd/google-cloud-github-runner)**,
Apache-2.0, unmodified. See `LICENSE`.

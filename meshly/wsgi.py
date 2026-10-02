"""Gunicorn entrypoint for the meshly build of the GitHub runner manager.

THIS FILE LIVES IN THE FORK, AND THAT IS THE POINT
--------------------------------------------------
This directory is an ADDITION to an otherwise byte-identical copy of
Cyclenerd/google-cloud-github-runner. Everything the vendor owns — `app/`,
`requirements.txt`, `Dockerfile`, `.github/` — is untouched, and nothing in
meshly-infra carries application code: it carries a 40-character submodule
pointer at this commit, a Cloud Build config, and the resulting image digest.

The pattern this implements is the SOFT FORK (see
meshly-infra:environments/github-runners/manager/README.md for the full
statement and the gate that enforces it). Its three rules:

  1. Upstream arrives as a submodule pointed at a meshly-owned FORK, never at
     the vendor directly — so our commits have somewhere to live.
  2. Our code is an ADDITION inside that fork, attached through an UPSTREAM
     EXTENSION POINT. No vendor file is ever edited.
  3. An upstream bump is a pointer diff plus a mechanical
     `git log vendor/master..HEAD` of what we are accepting.

Rule 2 is the load-bearing one, and this application has exactly the extension
point it needs: `create_app()`.

WHY NOT THE OBVIOUS ALTERNATIVES
--------------------------------
  * Edit `app/` directly. Then every vendor bump is a merge of code we did not
    write, and the worst case is a patch that applies WITH FUZZ — it succeeds
    and means something different.
  * Carry a patch series in the consuming repo. Same failure, plus the patches
    are reviewed in a different repo from the code they modify.
  * Pin it as a dependency. Not available: the vendor ships no pyproject.toml
    and no setup.py, only requirements.txt, so `pip install` from git fails
    with "no installable project found". It is a bare application directory,
    importable only with its root on sys.path. That absence is exactly why a
    submodule is the right carrier.

WHY COMPOSITION IS SAFE HERE, measured at the vendor commit rather than assumed
-------------------------------------------------------------------------------
  app/__init__.py:10-58   `create_app()` is a factory. It builds the Flask
                          object inside the function and returns it at :58,
                          registering both blueprints at :55-56. There is NO
                          module-level Flask singleton anywhere in the tree,
                          so importing the vendor does not commit us to its
                          wiring.
  import side effects     None that matter. Config reads use
                          `os.environ.get(...)`, never the raising subscript
                          form, so an import cannot die on missing config. The
                          one class touching Secret Manager is constructed
                          lazily INSIDE route handlers, so no credential is
                          needed to import.
  interposition           Zero `after_request` and zero `errorhandler` under
                          app/. The only hook is app/routes/setup.py:36
                          `before_request`, and it is BLUEPRINT-scoped to
                          /setup/*. Nothing the vendor ships sits between a
                          WSGI wrapper installed here and a request.
  LICENSE                 Apache-2.0. Redistribution of a build we produce is
                          permitted with attribution, and the vendor's LICENSE
                          travels inside the image unmodified.

IMPORT RESOLUTION — no PYTHONPATH, deliberately
-----------------------------------------------
The vendor's Dockerfile does `WORKDIR /app` then `COPY . .`, so this tree lands
with the vendor's `app/` at /app/app and this package at /app/meshly. Gunicorn
inserts its cwd on sys.path, so `from app import create_app` and
`meshly.wsgi:app` both resolve with no PYTHONPATH entry and no sys.path
manipulation. That is a consequence of putting our code INSIDE the fork rather
than beside it: the previous layout kept two separate trees and needed
`PYTHONPATH=/app/upstream:/app` to bridge them, which was one more thing to get
wrong for no benefit.

THE VENDOR'S CMD IS NOT EDITED
------------------------------
The vendor's Dockerfile ends `CMD ["gunicorn", "run:app"]`, which runs the
vendor's entrypoint, not ours. Changing that line would be an edit to a vendor
path — the one thing this whole arrangement forbids. So it is not changed. The
container command is overridden one layer up, in the Cloud Run service
definition (meshly-infra:environments/github-runners/manager.tf), to
`gunicorn meshly.wsgi:app`.

That has a real cost, stated here because it is surprising: running this image
with no command override runs the VENDOR'S app, not ours. The image is not
self-describing. meshly-infra asserts the override is present on the resolved
Cloud Run service (scripts/manager_image_provenance_check.py), because a
dropped override would silently serve the vendor's application — which has
none of our routes and, later, none of our IP policy.

WHAT IS DELIBERATELY NOT HERE YET
---------------------------------
The IP-allowlist middleware and our own routes. They attach here, in exactly
two places:

  * `app.wsgi_app = IpPolicyMiddleware(app.wsgi_app, ...)` — WSGI level, which
    runs BEFORE Flask routing and therefore before the inline
    X-Hub-Signature-256 HMAC check in app/routes/webhook.py. That ordering is
    correct for defence in depth and it is also the hazard: an IP-allowlist bug
    blocks GitHub BEFORE HMAC can validate, which makes the IP layer strictly
    more load-bearing than the control it backstops. Hence that change ships
    log-only first, with the "no webhooks arriving" alarm built before
    enforcement rather than after.
  * `app.register_blueprint(...)` — for meshly routes (`/runner/preempted` is
    the first), after create_app() has registered the vendor's two.

Until then this module is pure composition and should stay boring. If it grows
logic that is not "assemble the app", that logic belongs in a sibling module
under meshly/ that this file imports.
"""

import os

from dotenv import load_dotenv

from app import create_app

# Mirrors the vendor's run.py:12. A no-op in Cloud Run, where there is no .env
# file and every variable arrives from the service definition — kept because
# running this module locally should behave the way running the vendor's
# entrypoint locally behaves, and because load_dotenv() does not override
# variables that are already set, so it cannot shadow Cloud Run's env.
load_dotenv()

app = create_app()


if __name__ == "__main__":
    # Local convenience only; the container never takes this path (gunicorn
    # imports the module, it does not execute it as __main__). Binds to
    # loopback, matching the vendor's run.py:17 — a dev server on 0.0.0.0 is
    # how an unauthenticated /setup route ends up reachable from a coffee shop.
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", 8080)),
        debug=False,
    )

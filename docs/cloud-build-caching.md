# Cloud Build caching notes for the manager image

The manager image is small and its build is dominated by one step: compiling
Python wheels. These are notes on keeping that fast, and on the ways a cache
makes a build *wrong* rather than slow.

## What actually costs time

Upstream's Dockerfile is a two-stage build: a builder stage that runs
`pip wheel` into a wheelhouse (needing `build-base`), and a production stage
that installs those wheels and never needs a compiler. Almost all the wall
clock is in the first stage.

So the only cache that matters is the one that lets you skip it.

## Order your COPY so the wheelhouse survives an edit

Upstream already does this, and it is the single highest-value thing in the
build — worth understanding before you reorganise anything:

```dockerfile
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt
# ... application source copied LATER, in the production stage
```

Because only `requirements.txt` is in context when the expensive layer runs,
editing application code does not invalidate it. Copy the source in before
that `RUN` — which looks tidier — and every one-line code change recompiles
every wheel.

If you add your own code to the image, copy it **after** upstream's tree for
the same reason: upstream changes rarely (a pin bump), your code changes often,
and layer order should follow change frequency.

## Getting a cache at all

`gcloud builds submit` starts from a clean worker, so there is no local layer
cache to reuse. Two options:

1. **`--cache-from` against the previous image.** Pull the last build and offer
   it as a cache source. Cheap to set up; it works because the wheelhouse layer
   is keyed on `requirements.txt`, which is usually unchanged.

   The gotcha: a cache source that cannot be pulled is **not an error**. The
   build silently proceeds without a cache and simply takes longer, which is
   indistinguishable from a cache miss. If build time matters, assert it — a
   build that is quietly 4× slower every time is a cost nobody notices because
   nothing failed.

2. **A bigger machine type.** For a compile-bound build, throwing cores at it
   is often cheaper per build than operating a cache, and it has no correctness
   surface at all. Try this before building cache infrastructure.

Measure before choosing. This build is small enough that the cache may not pay
for its own complexity.

## The source tarball has no git metadata

`gcloud builds submit` uploads a **source tarball**, not a git checkout. Inside
the build there is no `.git`, no commit, no submodule state.

That has a consequence worth stating, because it is easy to design around
incorrectly: **any check that needs git objects cannot run inside the build.**
If you verify something about your tree — that a vendored submodule matches its
upstream, say — that check has to run in the wrapper that invokes the submit,
not in the build config. Put it in the `just`/`make` recipe that performs the
submit, and make that recipe the documented entry point rather than a bare
`gcloud builds submit`, or the check is one typed command away from being
skipped.

Related: if the build needs a submodule's contents, they must be present in the
directory you submit. An uninitialised submodule is an **empty directory**, and
`COPY` of an empty directory succeeds. The build then produces an image missing
the code it was supposed to contain, with no error anywhere.

## Pick the build context deliberately

If your build needs two sibling trees — upstream's and your own additions — the
context has to be their common parent, which is not the repository root and not
either tree. Say so in a comment next to the Dockerfile; it is the first thing
that confuses someone running the build by hand.

Then use `.gcloudignore` to keep the upload small, and check what it excludes:
excluding `LICENSE` is the one that matters, because Apache-2.0 requires the
licence to travel with a redistributed build and nothing will tell you it is
missing.

## Reproducibility, honestly

`ARG PYTHON_VERSION=3.14-alpine` is a **tag**, not a digest, so two builds of
the same source months apart are not guaranteed to be the same image. That is
a deliberate trade — you get base-image security updates without touching the
Dockerfile.

If you need the stronger property, pin the base by digest and accept that you
now own updating it. Do not claim reproducibility you do not have: pin it or
say it is unpinned, because the middle position — a tag plus a belief — is the
one that produces a surprise.

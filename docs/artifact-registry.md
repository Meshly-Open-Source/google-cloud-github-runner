# Artifact Registry notes for a self-built manager image

Upstream ships a Cloud Build template that builds the manager image for you.
These are notes for the case where you build it **yourself**, into **your own**
Artifact Registry, because you want the build config to live in your
infrastructure repository rather than be invoked out-of-tree.

Nothing here is required to use the project. It is the set of things we wished
someone had written down.

## Why you might build it yourself

One reason, and it is not "customisation": **the tree you review and the
artifact you run should be the same thing.** A build invoked from outside your
repository is a build nobody reviews — the same defect shape as a deploy script
generated at deploy time. Moving the build config in-tree makes the build a
reviewable object.

If you do not have that concern, use upstream's template. It is less work and
it is maintained.

## Repository layout

```
<region>-docker.pkg.dev/<project>/<repo>/<image>
```

* **Co-locate the repository with the Cloud Run region** that pulls from it.
  A cross-region pull is a cold-start cost paid on a scale-to-zero service,
  which is the one place it is most visible.
* **A dedicated repository, not a shared one.** Cleanup policies and IAM are
  both per-repository, so sharing one across unrelated images means every
  retention rule and every reader grant is the union of everyone's needs. The
  manager image is small and the repository is free; the coupling is not.
* **Separate repositories per environment** if you promote images between
  environments. Promotion then means a copy you can audit, rather than a tag
  move you cannot.

## Pin by digest, deploy by digest

Pull `...@sha256:<digest>`, never `:latest` and preferably not a mutable tag.

This matters more than it looks on a scale-to-zero service. A tag is a pointer
someone can move; if your service only pulls on cold start, a moved tag means
the running revision and the next one silently differ — and you find out hours
later, from whichever instance happened to start after the move. A digest
cannot do that.

Two things follow:

* **Enable immutable tags** on the repository if your workflow tolerates it.
  It converts "someone retagged over the release" from an incident into a
  push failure.
* **Make the deploy path assert the digest it is deploying** is the one the
  build produced, rather than resolving a tag at deploy time. A deploy that
  resolves a tag is a deploy whose input is decided by whoever pushed last.

## Cleanup policies, and the one that bites

Set a cleanup policy — untagged images accumulate forever otherwise, and each
rebuild of an unchanged layer set can leave one behind.

The trap: a policy that deletes untagged images will delete **the digest your
production service is pinned to**, because a digest-pinned image is untagged
from Artifact Registry's point of view unless something also tagged it. The
deletion is silent and the service keeps running — until the next cold start,
which fails to pull, at an unrelated time, with no change having been
deployed.

So either:

* keep a tag on anything deployed (and accept tags as retention markers), or
* write the policy to keep the most recent *N* versions regardless of tag
  state, or
* exclude digests that are currently referenced by a live service.

Whichever you choose, the policy is worth testing in dry-run mode first. The
failure is delayed, which makes it expensive to diagnose.

## Permissions

* The build identity needs write to the one repository. Not project-wide
  `artifactregistry.writer`.
* The **runtime** service account needs `roles/artifactregistry.reader` on that
  repository. This is easy to miss when the build and the service run as
  different identities, and the symptom is a deploy that succeeds and a
  revision that never becomes healthy — the pull failure is in the revision's
  logs, not in the deploy output.
* Prefer Workload Identity Federation over a service-account key for CI. Keyless
  is less work to operate once it is set up, and there is no key to rotate or
  leak.

## Licence note, if you redistribute

Upstream is Apache-2.0, which permits building and redistributing a derivative
image provided the licence and attribution travel with it. If you build your own
image, make sure `LICENSE` ends up **inside** it alongside the code it covers,
and check that no `.dockerignore` rule excludes it. It is a one-line omission
that turns a permitted redistribution into an unlicensed one, silently.

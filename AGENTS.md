<!-- ╔══════════════════════════════════════════════════════════════════════╗
     ║  FORK-MODIFIED FILE — DO NOT INCLUDE IN A PULL REQUEST TO UPSTREAM.  ║
     ║  Doing so would silently replace a maintainer's own agent            ║
     ║  instructions with ours. Check `git diff --name-only                 ║
     ║  upstream/master...HEAD` before opening one.                         ║
     ╚══════════════════════════════════════════════════════════════════════╝ -->

> # ⚠️ Read [`AGENTS-LOCAL.md`](AGENTS-LOCAL.md) first
>
> **This repository is a [soft fork](AGENTS-LOCAL.md#what-this-repository-is)**
> of [Cyclenerd/google-cloud-github-runner](https://github.com/Cyclenerd/google-cloud-github-runner),
> maintained by [meshly.ai](https://meshly.ai). It **tracks** upstream rather
> than diverging from it: we add directories, we do not modify upstream's code,
> and an upstream bump is meant to be a fast-forward.
>
> That constraint changes what you are allowed to do here, so the fork's rules
> come first:
>
> | Read | For |
> |---|---|
> | **[`AGENTS-LOCAL.md`](AGENTS-LOCAL.md)** | **Repo-wide agent rules. Mandatory.** The read-only boundary, how to route a change, what must never go upstream. |
> | [`RUNNER.xml`](RUNNER.xml) | Machine-readable manifest: per-path permissions, real route set, composition surface, build traps, what is and is not verified. |
> | [`README.md`](README.md) | Human entry point; what the fork adds. |
> | This file, below | Upstream's own architecture overview. Still accurate — the application is unmodified. |
>
> **The one rule:** upstream's tree is read-only here. Everything we add is a
> new top-level path. If a change seems to require editing `app/`, `gcp/`,
> `tools/`, the `Dockerfile` or `requirements.txt`, it belongs
> [upstream](https://github.com/Cyclenerd/google-cloud-github-runner/issues) —
> or it can be done by composition from outside upstream's tree.
>
> **What the fork adds:** `ipfilter/` (a framework-agnostic IP allowlist,
> stdlib-only, not wired into the application) and `docs/` (notes on building
> your own image). Both were written by an AI agent under human review; see
> [the disclosure](README.md#%EF%B8%8F-ai-generated-code-disclosure).

---

# Upstream's AGENTS.md

Everything below this line is upstream's, retained because it is accurate and
useful: this fork does not modify the application it describes. Treat it as
upstream's documentation — corrections to it belong upstream.

---

## System Architecture

This document provides a high-level overview of the `google-cloud-github-runner` system, a self-hosted GitHub Actions Runners manager to start ephemeral Google Compute Engine (GCE) instances to run the CI jobs. It manages the lifecycle of these runners, ensuring they are registered with GitHub and deleted after use.

## Components

### 1. Flask Application (`app/`)
The core logic resides in a Flask web application.
- **Webhook Handler (`app/routes/webhook.py`)**: Receives `workflow_job` events from GitHub.
- **Webhook Service (`app/services/webhook_service.py.py`)**: Orchestrates the runner creation process.
- **GCloud Client (`app/clients/gcloud_client.py`)**: Interacts with Google Cloud APIs to create and delete instances.
- **GitHub Client (`app/clients/github_client.py`)**: Interacts with GitHub APIs to generate registration tokens and manage runners.

### 2. Google Cloud Infrastructure (`gcp/`)
The infrastructure is managed via Terraform.
- **Cloud Run**: Hosts the Python Flask application.
- **Compute Engine**: Runs the ephemeral GitHub runners.
- **Secret Manager**: Stores sensitive secrets (GitHub App private key, webhook secret).
- **Cloud Build**: Builds the Docker image for the Flask app.

## Workflows

### Runner Creation Flow
1. **Webhook**: GitHub sends a `workflow_job.queued` event to the Flask app.
2. **Validation**: The app validates the webhook signature and checks if the job labels match a supported runner template.
3. **Token Generation**: The app requests a runner registration token from GitHub.
4. **Instance Creation**: The app creates a GCE instance using a startup script that installs the GitHub runner agent and registers it with the token.

### Runner Cleanup Flow
- **Ephemeral Runners**: The runners are configured to be ephemeral (run once and terminate).
- **GCE Deletion**: GitHub sends a `workflow_job.completed` event to the Flask app. The GCE instance with the runner ID is deleted.

## Directory Structure

- `app/`: Python source code for the Flask application.
- `gcp/`: Terraform configuration for Google Cloud resources.
- `tests/`: Pytest test suite.
- `scripts/`: Utility scripts.

## Technologies Used

*   **Backend:** Python, Flask, Google Cloud SDK
*   **Frontend:** HTML, Jinja, JavaScript

## Python Coding Style

Follow these coding style rules when writing Python code:

*   **Linter:** Code must pass `flake8 --ignore=W292,W503 --max-line-length=127 --show-source --statistics *.py app/*.py app/routes/*.py app/services/*.py app/clients/*.py app/utils/*.py tests/*.py tests/integration/*.py tests/unit/*.py`
*   **Line Length:** Maximum line length is 127 characters
*   **Blank Lines:** No blank line should contain whitespace (trailing whitespace is not allowed)
*   **End of File:** W292 is ignored (no blank line required at end of file)
*   **Binary Operator:** W503 for line break before binary operator is ignored
*   **Spaces:** Indent with spaces

## Terraform Coding Style

Follow these coding style rules when writing Terraform code:

*   **Format:** Code must pass `terraform fmt -recursive -check -diff gcp`
*   **Linter:** Code must pass `tflint --chdir gcp`
*   **Security:** Code must pass `tfsec gcp`
*   **Spaces:** Indent with spaces

## Bash and Shell Script Coding Style

Follow these coding style rules when writing Terraform code:

*   **Linter:** Code must pass `shellcheck tools/*.sh && shellcheck gcp/*.sh && shellcheck gcp/startup/*.sh`
*   **Tabs:** Indent with tabs

## Testing

Follow these guidelines when working with tests:

*   **Test Framework:** Use pytest for all test cases
*   **Test Location:** Write test cases in the `tests/` directory
*   **Running Tests:** Always run tests after making changes using `python -m pytest tests/ -v`
*   **Test Coverage:** When adding new features or modifying existing code, write corresponding test cases
*   **Test Verification:** After writing test cases, run them to ensure they pass

Example commands:
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_api.py -v

# Run tests with coverage
python -m pytest tests/ --cov
```

"""meshly-owned additions to the vendored runner-manager application.

This package is the ONLY non-vendor code in this repository. Every path outside
it is byte-identical to Cyclenerd/google-cloud-github-runner at the commit this
branch descends from, and meshly-infra's divergence gate fails closed if that
stops being true. See wsgi.py for the pattern and why it is shaped this way.
"""

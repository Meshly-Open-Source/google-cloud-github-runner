"""Make the package importable when run with `-c ipfilter/pytest.ini`.

The repository is not an installable project (no pyproject.toml, no setup.py),
so its own tests put the tree root on sys.path the same way. This mirrors that
rather than inventing a second convention.
"""

import sys
from pathlib import Path

TREE_ROOT = Path(__file__).resolve().parents[2]
if str(TREE_ROOT) not in sys.path:
    sys.path.insert(0, str(TREE_ROOT))

import sys
from pathlib import Path

# Ensure project root is importable when tests are run without PYTHONPATH set.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

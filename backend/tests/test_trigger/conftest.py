from pathlib import Path
import sys

# Ensure tests can import the backend package as `app` regardless of shell PYTHONPATH.
BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

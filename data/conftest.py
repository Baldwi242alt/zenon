# Lets pytest import the sunchaser_data package when run from the repo root
# (python -m pytest data/tests) or from inside data/.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

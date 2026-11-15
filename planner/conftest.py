# Lets pytest import the sunchaser package when run from the repo root
# (python -m pytest planner/tests) or from inside planner/.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

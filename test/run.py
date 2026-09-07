"""Run offline checks from any working directory: python3 test/run.py."""
import importlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
suite = unittest.TestSuite()
for path in sorted(Path(__file__).parent.glob("test_*.py")):
    module = importlib.import_module(path.stem)
    for name in sorted(vars(module)):
        if name.startswith("test_") and callable(getattr(module, name)):
            suite.addTest(unittest.FunctionTestCase(getattr(module, name)))
if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())

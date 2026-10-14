"""
index.py - entrypoint that Vercel detects automatically.

The real application lives in app/app.py. This file loads it by path and
exposes it as `app`, which is the name Vercel looks for.
"""

import importlib.util
import os
import sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")
sys.path.insert(0, BASE)        # so app.py can `import storage`, `models`, ...

_spec = importlib.util.spec_from_file_location(
    "lostfound_app", os.path.join(BASE, "app.py"))
_module = importlib.util.module_from_spec(_spec)
sys.modules["lostfound_app"] = _module
_spec.loader.exec_module(_module)

app = _module.app

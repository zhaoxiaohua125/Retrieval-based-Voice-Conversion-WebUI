"""客户端入口（保留 .py，逻辑在 run_ui_skeleton 模块）。"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from scripts.run_ui_skeleton import main

if __name__ == '__main__':
    raise SystemExit(main())

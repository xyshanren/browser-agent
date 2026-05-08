"""视觉模块 — POI 检测 JS + 截图标注"""

import importlib.resources as pkg_resources
from pathlib import Path

# find_pois.js 路径（供 browser.py 直接读取）
POI_JS_PATH = Path(__file__).parent / "find_pois.js"

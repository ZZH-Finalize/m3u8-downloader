#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动前端 CLI 工具
"""

import sys
from pathlib import Path

# 添加 frontend 目录到路径
frontend_dir = Path(__file__).parent / "frontend"
sys.path.insert(0, str(frontend_dir))

from cli import main

if __name__ == "__main__":
    main()

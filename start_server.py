#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动后端 API 服务
"""

import sys
from pathlib import Path

# 添加 backend 目录到路径
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from server import main

if __name__ == "__main__":
    main()

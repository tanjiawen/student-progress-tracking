#!/usr/bin/env python3
"""一键初始化脚本.

按顺序执行:
1. init_db.py   — 创建数据库表
2. seed_data.py — 注入基础种子数据
3. seed_exam.py — 注入测试考试数据

用法:
    cd backend && .venv/bin/python scripts/run_all.py
    cd backend && .venv/bin/python scripts/run_all.py --alembic
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.init_db import main as init_db_main
from scripts.seed_data import main as seed_data_main
from scripts.seed_exam import main as seed_exam_main


async def main() -> None:
    parser = argparse.ArgumentParser(description="一键初始化数据库并注入种子数据")
    parser.add_argument(
        "--alembic",
        action="store_true",
        help="使用 alembic upgrade head 初始化数据库表",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🚀  student-progress-tracking 一键初始化")
    print("=" * 60)

    # 步骤 1: 初始化数据库
    print("\n【步骤 1/3】初始化数据库...")
    if args.alembic:
        sys.argv = ["init_db.py", "--alembic"]
    else:
        sys.argv = ["init_db.py"]
    await init_db_main()

    # 步骤 2: 注入基础种子数据
    print("\n【步骤 2/3】注入基础种子数据...")
    sys.argv = ["seed_data.py"]
    await seed_data_main()

    # 步骤 3: 注入测试考试数据
    print("\n【步骤 3/3】注入测试考试数据...")
    sys.argv = ["seed_exam.py"]
    await seed_exam_main()

    print("\n" + "=" * 60)
    print("🎉 所有初始化步骤已完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""数据库初始化脚本.

用法:
    cd backend && .venv/bin/python scripts/init_db.py
    cd backend && .venv/bin/python scripts/init_db.py --alembic
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import inspect

from app.core.database import engine, init_db


def run_alembic_upgrade() -> None:
    """执行 alembic upgrade head (使用子进程避免事件循环冲突)."""
    import subprocess

    alembic_ini = PROJECT_ROOT / "alembic.ini"
    if not alembic_ini.exists():
        raise FileNotFoundError(f"alembic.ini 不存在: {alembic_ini}")

    cmd = [sys.executable, "-m", "alembic", "upgrade", "head"]
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic upgrade failed:\n{result.stderr}")
    if result.stdout:
        print(result.stdout.strip())


async def create_all_tables() -> list[str]:
    """使用 SQLModel.metadata.create_all 创建所有表."""
    await init_db()
    async with engine.begin() as conn:
        tables = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
    return tables


async def list_tables() -> list[str]:
    """获取当前数据库中的所有表名."""
    async with engine.begin() as conn:
        tables = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
    return tables


async def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize database tables")
    parser.add_argument(
        "--alembic",
        action="store_true",
        help="使用 alembic upgrade head 代替 SQLModel.metadata.create_all",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("🗄️  数据库初始化")
    print("=" * 50)

    try:
        if args.alembic:
            print("🚀 执行 alembic upgrade head...")
            run_alembic_upgrade()
            print("✅ Alembic 迁移完成")
        else:
            print("🚀 使用 SQLModel.metadata.create_all 创建表...")
            tables = await create_all_tables()
            print(f"✅ 表创建完成")

        tables = await list_tables()
        print(f"\n📊 数据库中共有 {len(tables)} 张表:")
        for t in sorted(tables):
            print(f"   - {t}")

        print("\n🎉 数据库初始化完成!")
    except Exception as e:
        print(f"\n❌ 初始化失败: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

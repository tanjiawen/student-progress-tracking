#!/usr/bin/env python3
"""Qdrant 初始化脚本.

创建 collection 并检查连接状态.
"""

import asyncio
import sys

from app.services.qdrant_service import QdrantService


async def main() -> int:
    service = QdrantService()

    print(f"🔌 正在连接 Qdrant: {service.client._base_url}...")

    try:
        await service.ensure_collection()
    except ConnectionError as e:
        print(f"❌ {e}")
        return 1

    print(f"✅ Collection '{service.collection_name}' 已就绪")

    try:
        count = await service.count()
        print(f"📊 当前向量数量: {count}")
    except Exception as e:
        print(f"⚠️ 获取向量数量失败: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

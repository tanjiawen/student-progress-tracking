"""知识点服务 — 负责知识点树的创建、路径查询、前置依赖及课标导入."""

from __future__ import annotations

import json
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.knowledge_point import KnowledgePoint
from app.models.knowledge_relation import KnowledgeRelation, RelationType
from app.repositories.knowledge_point import KnowledgePointRepository
from app.repositories.knowledge_relation import KnowledgeRelationRepository
from app.repositories.subject import SubjectRepository


class KnowledgePointService:
    """知识点业务服务，编排知识点相关的 Repository."""

    def __init__(self, session: AsyncSession) -> None:
        self.kp_repo = KnowledgePointRepository(session)
        self.relation_repo = KnowledgeRelationRepository(session)
        self.subject_repo = SubjectRepository(session)
        self.session = session

    async def create_knowledge_tree(
        self, subject_id: int, tree_data: list[dict]
    ) -> dict:
        """批量创建知识点树.

        tree_data 中每项可包含：
        - code, name, description, level, parent_code, sort_order, is_leaf
        - 若提供 parent_code 则自动映射为 parent_id

        Service 层控制事务，一次性 commit.

        Args:
            subject_id: 学科 ID
            tree_data: 知识点节点列表

        Returns:
            dict: 创建结果统计
        """
        subject = await self.subject_repo.get_by_id(subject_id)
        if not subject:
            raise NotFoundException(f"学科 {subject_id} 不存在")

        # 建立 code -> 创建后 id 的映射，用于处理 parent 关联
        code_to_id: dict[str, int] = {}
        created_nodes: list[KnowledgePoint] = []

        # 第一轮：创建所有节点（不处理 parent_id）
        for item in tree_data:
            code = item.get("code")
            if not code:
                raise BadRequestException(
                    f"知识点 code 为必填字段，数据: {item}"
                )

            node = KnowledgePoint(
                subject_id=subject_id,
                parent_id=None,
                code=code,
                name=item.get("name", code),
                description=item.get("description"),
                level=item.get("level", 1),
                sort_order=item.get("sort_order", 0),
                is_leaf=item.get("is_leaf", False),
            )
            self.session.add(node)
            created_nodes.append(node)

        await self.session.flush()

        # 收集 code -> id 映射
        for node in created_nodes:
            code_to_id[node.code] = node.id

        # 第二轮：处理 parent_code -> parent_id
        for item in tree_data:
            code = item.get("code")
            parent_code = item.get("parent_code")
            if parent_code and parent_code in code_to_id:
                node_id = code_to_id[code]
                parent_id = code_to_id[parent_code]
                for node in created_nodes:
                    if node.id == node_id:
                        node.parent_id = parent_id
                        self.session.add(node)
                        break

        await self.session.commit()

        return {
            "subject_id": subject_id,
            "created_count": len(created_nodes),
            "codes": list(code_to_id.keys()),
        }

    async def get_knowledge_path(self, kp_id: int) -> list[dict]:
        """获取从根到该知识点的完整路径.

        Args:
            kp_id: 知识点 ID

        Returns:
            list[dict]: 从根节点到目标节点的路径列表
        """
        kp = await self.kp_repo.get_by_id(kp_id)
        if not kp:
            raise NotFoundException(f"知识点 {kp_id} 不存在")

        path = await self.kp_repo.get_path_to_root(kp_id)
        # 反转：根 -> 目标
        path.reverse()
        return [
            {
                "id": node.id,
                "code": node.code,
                "name": node.name,
                "level": node.level,
            }
            for node in path
        ]

    async def get_prerequisites(self, kp_id: int) -> list[dict]:
        """获取所有前置知识点（递归）.

        Args:
            kp_id: 知识点 ID

        Returns:
            list[dict]: 前置知识点列表
        """
        kp = await self.kp_repo.get_by_id(kp_id)
        if not kp:
            raise NotFoundException(f"知识点 {kp_id} 不存在")

        prereq_ids = await self.relation_repo.get_prerequisites(kp_id)
        if not prereq_ids:
            return []

        # 去重并保持顺序
        seen: set[int] = set()
        unique_ids: list[int] = []
        for pid in prereq_ids:
            if pid not in seen:
                seen.add(pid)
                unique_ids.append(pid)

        nodes = []
        for pid in unique_ids:
            node = await self.kp_repo.get_by_id(pid)
            if node:
                nodes.append(
                    {
                        "id": node.id,
                        "code": node.code,
                        "name": node.name,
                        "level": node.level,
                    }
                )
        return nodes

    async def import_standard_curriculum(
        self, subject_code: str, curriculum_file: str
    ) -> dict:
        """从 JSON 文件导入标准课标知识点树.

        JSON 格式示例:
        [
          {
            "code": "M.1.1",
            "name": "有理数",
            "level": 1,
            "children": [...]
          }
        ]

        Args:
            subject_code: 学科代码
            curriculum_file: JSON 文件路径

        Returns:
            dict: 导入结果
        """
        subject = await self.subject_repo.get_by_code(subject_code)
        if not subject:
            raise NotFoundException(f"学科代码 {subject_code} 不存在")

        try:
            with open(curriculum_file, "r", encoding="utf-8") as f:
                raw_data: list[dict[str, Any]] = json.load(f)
        except FileNotFoundError as exc:
            raise BadRequestException(
                f"文件不存在: {curriculum_file}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise BadRequestException(
                f"JSON 解析失败: {exc}"
            ) from exc

        # 将嵌套结构拍平为 tree_data 格式
        flat_nodes: list[dict] = []

        def _flatten(nodes: list[dict], parent_code: str | None = None) -> None:
            for node in nodes:
                flat_node = {
                    "code": node["code"],
                    "name": node["name"],
                    "description": node.get("description"),
                    "level": node.get("level", 1),
                    "sort_order": node.get("sort_order", 0),
                    "is_leaf": not node.get("children"),
                    "parent_code": parent_code,
                }
                flat_nodes.append(flat_node)
                if node.get("children"):
                    _flatten(node["children"], node["code"])

        _flatten(raw_data)

        result = await self.create_knowledge_tree(subject.id, flat_nodes)
        result["subject_code"] = subject_code
        return result

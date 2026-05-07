#!/usr/bin/env python3
"""种子数据注入脚本.

注入基础数据：学科、用户、班级、学生、知识点树、知识点关系.

用法:
    cd backend && .venv/bin/python scripts/seed_data.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import async_session
from app.core.security import get_password_hash
from app.models import (
    Class,
    ClassStudent,
    KnowledgePoint,
    KnowledgeRelation,
    RelationType,
    Student,
    Subject,
    User,
    UserRole,
)

# ---------- 数据源 ----------

SUBJECTS_DATA = [
    {"name": "数学", "code": "MATH", "grade_levels": [7, 8, 9], "sort_order": 1},
    {"name": "语文", "code": "CHN", "grade_levels": [7, 8, 9], "sort_order": 2},
    {"name": "英语", "code": "ENG", "grade_levels": [7, 8, 9], "sort_order": 3},
    {"name": "道德与法治", "code": "POL", "grade_levels": [7, 8, 9], "sort_order": 4},
    {"name": "物理", "code": "PHY", "grade_levels": [8, 9], "sort_order": 5},
    {"name": "化学", "code": "CHE", "grade_levels": [9], "sort_order": 6},
]

USERS_DATA = [
    {
        "username": "admin",
        "email": "admin@school.com",
        "password": "admin123",
        "real_name": "系统管理员",
        "role": "admin",
    },
    {
        "username": "teacher1",
        "email": "teacher1@school.com",
        "password": "teacher123",
        "real_name": "张老师",
        "role": "teacher",
    },
    {
        "username": "student1",
        "email": "student1@school.com",
        "password": "student123",
        "real_name": "谭子凌",
        "role": "student",
    },
]

CLASS_DATA = {
    "name": "八(28)班",
    "grade": "八年级",
    "academic_year": "2025-2026",
    "semester": "春季",
}

# 道德与法治-八年级下册 知识点树
KNOWLEDGE_TREE = [
    {
        "name": "道德与法治-八下",
        "code": "POL-8B",
        "level": 1,
        "is_leaf": False,
        "sort_order": 1,
        "children": [
            {
                "name": "第一单元 坚持宪法至上",
                "code": "POL-8B-1",
                "level": 2,
                "is_leaf": False,
                "sort_order": 1,
                "children": [
                    {
                        "name": "1.1 维护宪法权威",
                        "code": "POL-8B-1-1",
                        "level": 3,
                        "is_leaf": False,
                        "sort_order": 1,
                        "children": [
                            {
                                "name": "1.1.1 宪法是国家的根本法",
                                "code": "POL-8B-1-1-1",
                                "level": 4,
                                "is_leaf": True,
                                "sort_order": 1,
                            },
                            {
                                "name": "1.1.2 宪法的最高法律地位",
                                "code": "POL-8B-1-1-2",
                                "level": 4,
                                "is_leaf": True,
                                "sort_order": 2,
                            },
                        ],
                    },
                    {
                        "name": "1.2 保障宪法实施",
                        "code": "POL-8B-1-2",
                        "level": 3,
                        "is_leaf": False,
                        "sort_order": 2,
                        "children": [
                            {
                                "name": "1.2.1 依宪治国",
                                "code": "POL-8B-1-2-1",
                                "level": 4,
                                "is_leaf": True,
                                "sort_order": 1,
                            },
                            {
                                "name": "1.2.2 宪法监督",
                                "code": "POL-8B-1-2-2",
                                "level": 4,
                                "is_leaf": True,
                                "sort_order": 2,
                            },
                        ],
                    },
                ],
            },
            {
                "name": "第二单元 理解权利义务",
                "code": "POL-8B-2",
                "level": 2,
                "is_leaf": False,
                "sort_order": 2,
                "children": [
                    {
                        "name": "2.1 公民权利",
                        "code": "POL-8B-2-1",
                        "level": 3,
                        "is_leaf": False,
                        "sort_order": 1,
                        "children": [
                            {
                                "name": "2.1.1 依法行使权利",
                                "code": "POL-8B-2-1-1",
                                "level": 4,
                                "is_leaf": True,
                                "sort_order": 1,
                            },
                            {
                                "name": "2.1.2 不得损害他人合法权益",
                                "code": "POL-8B-2-1-2",
                                "level": 4,
                                "is_leaf": True,
                                "sort_order": 2,
                            },
                        ],
                    },
                    {
                        "name": "2.2 公民义务",
                        "code": "POL-8B-2-2",
                        "level": 3,
                        "is_leaf": False,
                        "sort_order": 2,
                        "children": [
                            {
                                "name": "2.2.1 坚持国家利益至上",
                                "code": "POL-8B-2-2-1",
                                "level": 4,
                                "is_leaf": True,
                                "sort_order": 1,
                            },
                        ],
                    },
                ],
            },
            {
                "name": "第三单元 人民当家作主",
                "code": "POL-8B-3",
                "level": 2,
                "is_leaf": False,
                "sort_order": 3,
                "children": [
                    {
                        "name": "3.1 根本政治制度",
                        "code": "POL-8B-3-1",
                        "level": 3,
                        "is_leaf": False,
                        "sort_order": 1,
                        "children": [
                            {
                                "name": "3.1.1 人民代表大会制度",
                                "code": "POL-8B-3-1-1",
                                "level": 4,
                                "is_leaf": True,
                                "sort_order": 1,
                            },
                            {
                                "name": "3.1.2 全国人大的立法权",
                                "code": "POL-8B-3-1-2",
                                "level": 4,
                                "is_leaf": True,
                                "sort_order": 2,
                            },
                        ],
                    },
                    {
                        "name": "3.2 基本政治制度",
                        "code": "POL-8B-3-2",
                        "level": 3,
                        "is_leaf": False,
                        "sort_order": 2,
                        "children": [
                            {
                                "name": "3.2.1 民族区域自治制度",
                                "code": "POL-8B-3-2-1",
                                "level": 4,
                                "is_leaf": True,
                                "sort_order": 1,
                            },
                            {
                                "name": "3.2.2 基层群众自治制度",
                                "code": "POL-8B-3-2-2",
                                "level": 4,
                                "is_leaf": True,
                                "sort_order": 2,
                            },
                        ],
                    },
                ],
            },
            {
                "name": "第四单元 崇尚法治精神",
                "code": "POL-8B-4",
                "level": 2,
                "is_leaf": False,
                "sort_order": 4,
                "children": [
                    {
                        "name": "4.1 尊重自由平等",
                        "code": "POL-8B-4-1",
                        "level": 3,
                        "is_leaf": True,
                        "sort_order": 1,
                    },
                    {
                        "name": "4.2 维护公平正义",
                        "code": "POL-8B-4-2",
                        "level": 3,
                        "is_leaf": True,
                        "sort_order": 2,
                    },
                ],
            },
        ],
    }
]

KNOWLEDGE_RELATIONS = [
    ("POL-8B-1-1-1", "POL-8B-1-1-2", RelationType.prerequisite),
    ("POL-8B-2-1-1", "POL-8B-2-1-2", RelationType.contains),
]


# ---------- 辅助函数 ----------


async def get_or_create_subject(session: AsyncSession, data: dict) -> int:
    stmt = select(Subject).where(Subject.code == data["code"])
    result = await session.exec(stmt)
    existing = result.first()
    if existing:
        print(f"   ⚠️ 学科已存在: {existing.name} (id={existing.id})")
        return existing.id
    subject = Subject(**data)
    session.add(subject)
    await session.commit()
    await session.refresh(subject)
    print(f"   ✅ 创建学科: {subject.name} (id={subject.id})")
    return subject.id


async def get_or_create_user(session: AsyncSession, data: dict) -> int:
    stmt = select(User).where(User.username == data["username"])
    result = await session.exec(stmt)
    existing = result.first()
    if existing:
        print(f"   ⚠️ 用户已存在: {existing.username} (id={existing.id})")
        return existing.id
    payload = data.copy()
    plain_password = payload.pop("password")
    payload["hashed_password"] = get_password_hash(plain_password)
    payload["role"] = UserRole(payload["role"])
    user = User(**payload)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    print(f"   ✅ 创建用户: {user.username} (id={user.id})")
    return user.id


async def get_or_create_class(
    session: AsyncSession, data: dict, subject_id: int, teacher_id: int
) -> int:
    stmt = select(Class).where(Class.name == data["name"])
    result = await session.exec(stmt)
    existing = result.first()
    if existing:
        print(f"   ⚠️ 班级已存在: {existing.name} (id={existing.id})")
        return existing.id
    cls = Class(
        name=data["name"],
        grade=data["grade"],
        subject_id=subject_id,
        teacher_id=teacher_id,
        academic_year=data["academic_year"],
        semester=data["semester"],
    )
    session.add(cls)
    await session.commit()
    await session.refresh(cls)
    print(f"   ✅ 创建班级: {cls.name} (id={cls.id})")
    return cls.id


async def get_or_create_student(
    session: AsyncSession, user_id: int, class_id: int
) -> int:
    stmt = select(Student).where(Student.user_id == user_id)
    result = await session.exec(stmt)
    existing = result.first()
    if existing:
        print(f"   ⚠️ 学生已存在: user_id={existing.user_id} (id={existing.id})")
        return existing.id
    # 检查 student_number 是否已被占用
    stmt2 = select(Student).where(Student.student_number == "24022845")
    result2 = await session.exec(stmt2)
    existing2 = result2.first()
    if existing2:
        print(f"   ⚠️ 学号 24022845 已被占用，跳过创建学生")
        return existing2.id
    student = Student(
        user_id=user_id,
        student_number="24022845",
        class_id=class_id,
        enrollment_year=2024,
    )
    session.add(student)
    await session.commit()
    await session.refresh(student)
    print(f"   ✅ 创建学生: user_id={student.user_id} (id={student.id})")
    return student.id


async def get_or_create_class_student(
    session: AsyncSession, class_id: int, student_id: int
) -> None:
    stmt = select(ClassStudent).where(
        ClassStudent.class_id == class_id,
        ClassStudent.student_id == student_id,
    )
    result = await session.exec(stmt)
    if result.first():
        print(f"   ⚠️ 班级学生关联已存在: class={class_id}, student={student_id}")
        return
    cs = ClassStudent(class_id=class_id, student_id=student_id)
    session.add(cs)
    await session.commit()
    print(f"   ✅ 创建班级学生关联: class={class_id}, student={student_id}")


async def create_knowledge_tree(
    session: AsyncSession, subject_id: int
) -> dict[str, int]:
    print("🌳 注入知识点树...")
    kp_map: dict[str, int] = {}

    async def _create_node(node: dict, parent_id: int | None) -> int:
        stmt = select(KnowledgePoint).where(KnowledgePoint.code == node["code"])
        result = await session.exec(stmt)
        existing = result.first()
        if existing:
            print(f"   ⚠️ 知识点已存在: {existing.name} (id={existing.id})")
            kp_map[existing.code] = existing.id
            node_id = existing.id
        else:
            kp = KnowledgePoint(
                subject_id=subject_id,
                parent_id=parent_id,
                code=node["code"],
                name=node["name"],
                level=node["level"],
                is_leaf=node["is_leaf"],
                sort_order=node["sort_order"],
            )
            session.add(kp)
            await session.commit()
            await session.refresh(kp)
            print(f"   ✅ 创建知识点: {kp.name} (id={kp.id})")
            kp_map[kp.code] = kp.id
            node_id = kp.id

        for child in node.get("children", []):
            await _create_node(child, node_id)
        return node_id

    for root in KNOWLEDGE_TREE:
        await _create_node(root, None)

    return kp_map


async def create_knowledge_relations(
    session: AsyncSession, kp_map: dict[str, int]
) -> None:
    print("🔗 注入知识点关系...")
    for source_code, target_code, rel_type in KNOWLEDGE_RELATIONS:
        source_id = kp_map[source_code]
        target_id = kp_map[target_code]
        stmt = select(KnowledgeRelation).where(
            KnowledgeRelation.source_kp_id == source_id,
            KnowledgeRelation.target_kp_id == target_id,
            KnowledgeRelation.relation_type == rel_type,
        )
        result = await session.exec(stmt)
        if result.first():
            print(
                f"   ⚠️ 关系已存在: {source_code} -> {target_code} ({rel_type.value})"
            )
            continue
        rel = KnowledgeRelation(
            source_kp_id=source_id,
            target_kp_id=target_id,
            relation_type=rel_type,
            weight=0.8,
        )
        session.add(rel)
        await session.commit()
        print(f"   ✅ 创建关系: {source_code} -> {target_code} ({rel_type.value})")


# ---------- 主流程 ----------


async def main() -> None:
    print("=" * 50)
    print("🌱 开始注入种子数据")
    print("=" * 50)

    try:
        async with async_session() as session:
            # 1. 学科
            subject_map: dict[str, int] = {}
            print("📚 注入学科...")
            for item in SUBJECTS_DATA:
                sid = await get_or_create_subject(session, item)
                subject_map[item["code"]] = sid

            # 2. 用户
            user_map: dict[str, int] = {}
            print("\n👤 注入用户...")
            for item in USERS_DATA:
                uid = await get_or_create_user(session, item)
                user_map[item["username"]] = uid

            # 3. 班级（道德与法治，teacher1）
            print("\n🏫 注入班级...")
            pol_subject_id = subject_map["POL"]
            teacher_id = user_map["teacher1"]
            class_id = await get_or_create_class(
                session, CLASS_DATA, pol_subject_id, teacher_id
            )

            # 4. 学生
            print("\n🎓 注入学生...")
            student_user_id = user_map["student1"]
            student_id = await get_or_create_student(session, student_user_id, class_id)
            await get_or_create_class_student(session, class_id, student_id)

            # 5. 知识点树
            print()
            kp_map = await create_knowledge_tree(session, pol_subject_id)

            # 6. 知识点关系
            print()
            await create_knowledge_relations(session, kp_map)

        print("\n" + "=" * 50)
        print("🎉 种子数据注入完成!")
        print("=" * 50)
        print(f"   学科数量: {len(subject_map)}")
        print(f"   用户数量: {len(user_map)}")
        print(f"   班级 ID : {class_id}")
        print(f"   学生 ID : {student_id}")
        print(f"   知识点数量: {len(kp_map)}")
    except Exception as e:
        print(f"\n❌ 种子数据注入失败: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

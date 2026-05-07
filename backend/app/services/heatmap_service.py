from __future__ import annotations

"""班级知识点掌握度热力图服务."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.knowledge_point import KnowledgePoint
from app.models.student import Student
from app.models.student_knowledge_state import StudentKnowledgeState


class HeatmapService:
    """班级知识点掌握度热力图服务."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate_class_heatmap(
        self,
        class_id: int,
        subject_id: int | None = None,
    ) -> dict:
        """生成热力图数据.

        返回格式：
        {
            "x_axis": ["学生1", "学生2", ...],
            "y_axis": ["知识点1", "知识点2", ...],
            "data": [[0.8, 0.6, ...], ...],
            "class_avg": 0.65,
            "weak_top5": [...],
        }
        """
        # 1. 获取班级所有学生
        stmt_students = (
            select(Student.id, Student.student_number)
            .where(Student.class_id == class_id)
            .order_by(Student.student_number)
        )
        result = await self.session.exec(stmt_students)
        student_rows = list(result.all())
        if not student_rows:
            return {
                "x_axis": [],
                "y_axis": [],
                "data": [],
                "class_avg": 0.0,
                "weak_top5": [],
            }

        student_ids = [s.id for s in student_rows]
        student_names = [s.student_number for s in student_rows]

        # 2. 获取学科下所有知识点（或指定知识点）
        kp_stmt = select(KnowledgePoint).where(KnowledgePoint.is_deleted.is_(False))
        if subject_id is not None:
            kp_stmt = kp_stmt.where(KnowledgePoint.subject_id == subject_id)
        kp_result = await self.session.exec(kp_stmt)
        kp_list = list(kp_result.all())
        if not kp_list:
            return {
                "x_axis": student_names,
                "y_axis": [],
                "data": [],
                "class_avg": 0.0,
                "weak_top5": [],
            }

        kp_ids = [kp.id for kp in kp_list]
        kp_names = [kp.name for kp in kp_list]
        kp_id_to_idx = {kp.id: i for i, kp in enumerate(kp_list)}

        # 3. SQL 聚合：查询每个学生在每个知识点的掌握度
        state_stmt = (
            select(
                StudentKnowledgeState.student_id,
                StudentKnowledgeState.knowledge_point_id,
                func.avg(StudentKnowledgeState.mastery_probability).label("mastery"),
            )
            .where(
                StudentKnowledgeState.student_id.in_(student_ids),
                StudentKnowledgeState.knowledge_point_id.in_(kp_ids),
            )
            .group_by(
                StudentKnowledgeState.student_id,
                StudentKnowledgeState.knowledge_point_id,
            )
        )
        state_result = await self.session.exec(state_stmt)
        state_rows = list(state_result.all())

        # 4. 组装矩阵数据（学生 × 知识点）
        # 初始化矩阵为 0.0
        matrix: list[list[float]] = [
            [0.0 for _ in kp_ids] for _ in student_ids
        ]
        student_id_to_idx = {sid: i for i, sid in enumerate(student_ids)}

        for row in state_rows:
            s_idx = student_id_to_idx.get(row.student_id)
            k_idx = kp_id_to_idx.get(row.knowledge_point_id)
            if s_idx is not None and k_idx is not None:
                matrix[s_idx][k_idx] = round(float(row.mastery), 3) if row.mastery else 0.0

        # 5. 计算班级平均掌握度、薄弱知识点 TOP5（按知识点聚合）
        avg_stmt = (
            select(
                StudentKnowledgeState.knowledge_point_id,
                func.avg(StudentKnowledgeState.mastery_probability).label("avg_mastery"),
                func.count(StudentKnowledgeState.id).label("student_count"),
            )
            .where(
                StudentKnowledgeState.student_id.in_(student_ids),
                StudentKnowledgeState.knowledge_point_id.in_(kp_ids),
            )
            .group_by(StudentKnowledgeState.knowledge_point_id)
        )
        avg_result = await self.session.exec(avg_stmt)
        avg_rows = list(avg_result.all())

        kp_avg_map: dict[int, float] = {}
        for row in avg_rows:
            kp_avg_map[row.knowledge_point_id] = round(float(row.avg_mastery), 3) if row.avg_mastery else 0.0

        # 填充未查询到的知识点平均值为 0.0
        class_avg_values = [kp_avg_map.get(kp_id, 0.0) for kp_id in kp_ids]
        overall_class_avg = round(sum(class_avg_values) / len(class_avg_values), 3) if class_avg_values else 0.0

        weak_top5 = sorted(
            [
                {
                    "knowledge_point_id": kp_id,
                    "knowledge_point_name": kp_names[i],
                    "avg_mastery": kp_avg_map.get(kp_id, 0.0),
                }
                for i, kp_id in enumerate(kp_ids)
            ],
            key=lambda x: x["avg_mastery"],
        )[:5]

        return {
            "x_axis": student_names,
            "y_axis": kp_names,
            "data": matrix,
            "class_avg": overall_class_avg,
            "weak_top5": weak_top5,
        }

    async def generate_knowledge_trend(
        self,
        class_id: int,
        knowledge_point_id: int,
        months: int = 3,
    ) -> dict:
        """单个知识点在班级中的掌握度趋势.

        返回历次考试的平均掌握度变化（按月汇总）.
        """
        since = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # 回退 N 个月
        for _ in range(months - 1):
            if since.month == 1:
                since = since.replace(year=since.year - 1, month=12)
            else:
                since = since.replace(month=since.month - 1)

        stmt_students = select(Student.id).where(Student.class_id == class_id)
        result = await self.session.exec(stmt_students)
        student_ids = [r.id for r in result.all()]
        if not student_ids:
            return {"class_id": class_id, "knowledge_point_id": knowledge_point_id, "trend": []}

        # 按月聚合平均掌握度
        trend_stmt = (
            select(
                func.date_trunc("month", StudentKnowledgeState.updated_at).label("month"),
                func.avg(StudentKnowledgeState.mastery_probability).label("avg_mastery"),
                func.count(StudentKnowledgeState.id).label("count"),
            )
            .where(
                StudentKnowledgeState.student_id.in_(student_ids),
                StudentKnowledgeState.knowledge_point_id == knowledge_point_id,
                StudentKnowledgeState.updated_at >= since,
            )
            .group_by(func.date_trunc("month", StudentKnowledgeState.updated_at))
            .order_by(func.date_trunc("month", StudentKnowledgeState.updated_at))
        )
        trend_result = await self.session.exec(trend_stmt)
        trend_rows = list(trend_result.all())

        trend = []
        for row in trend_rows:
            month_label = row.month.strftime("%Y-%m") if row.month else ""
            trend.append({
                "month": month_label,
                "avg_mastery": round(float(row.avg_mastery), 3) if row.avg_mastery else 0.0,
                "student_count": row.count,
            })

        return {
            "class_id": class_id,
            "knowledge_point_id": knowledge_point_id,
            "trend": trend,
        }

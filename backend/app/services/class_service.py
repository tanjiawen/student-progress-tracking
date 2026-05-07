"""班级服务 — 负责班级的创建、学生管理及详情查询."""

from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.class_ import Class
from app.models.class_student import ClassStudent
from app.models.student import Student
from app.repositories.class_ import ClassRepository
from app.repositories.exam import ExamRepository
from app.repositories.student import StudentRepository


class ClassService:
    """班级业务服务，编排班级相关的 Repository."""

    def __init__(self, session: AsyncSession) -> None:
        self.class_repo = ClassRepository(session)
        self.student_repo = StudentRepository(session)
        self.exam_repo = ExamRepository(session)
        self.session = session

    async def create_class(self, data: dict, teacher_id: int) -> dict:
        """创建班级.

        Args:
            data: 班级数据，需包含 name, grade, academic_year, semester 等
            teacher_id: 班主任/教师用户 ID

        Returns:
            dict: 创建后的班级信息
        """
        name = data.get("name")
        if not name:
            raise BadRequestException("班级名称 name 为必填字段")

        class_ = Class(
            name=name,
            grade=data.get("grade", ""),
            subject_id=data.get("subject_id"),
            teacher_id=teacher_id,
            academic_year=data.get("academic_year", ""),
            semester=data.get("semester", ""),
        )
        created = await self.class_repo.create(class_)

        return {
            "id": created.id,
            "name": created.name,
            "grade": created.grade,
            "teacher_id": created.teacher_id,
            "academic_year": created.academic_year,
            "semester": created.semester,
            "created_at": created.created_at,
        }

    async def add_students_to_class(
        self, class_id: int, student_ids: list[int]
    ) -> dict:
        """将多名学生加入班级.

        Args:
            class_id: 班级 ID
            student_ids: 学生 ID 列表

        Returns:
            dict: 操作结果
        """
        class_ = await self.class_repo.get_by_id(class_id)
        if not class_:
            raise NotFoundException(f"班级 {class_id} 不存在")

        added = []
        skipped = []

        for student_id in student_ids:
            student = await self.student_repo.get_by_id(student_id)
            if not student:
                skipped.append(
                    {"student_id": student_id, "reason": "学生不存在"}
                )
                continue

            # 更新学生主表的 class_id
            student.class_id = class_id
            self.session.add(student)

            # 维护多对多关联表
            assoc = ClassStudent(class_id=class_id, student_id=student_id)
            self.session.add(assoc)
            added.append(student_id)

        await self.session.commit()

        return {
            "class_id": class_id,
            "added_count": len(added),
            "skipped_count": len(skipped),
            "added_ids": added,
            "skipped": skipped,
        }

    async def get_class_detail(self, class_id: int) -> dict:
        """获取班级详情（班级信息 + 学生列表 + 考试列表）.

        Args:
            class_id: 班级 ID

        Returns:
            dict: 班级详情
        """
        class_ = await self.class_repo.get_by_id(class_id)
        if not class_:
            raise NotFoundException(f"班级 {class_id} 不存在")

        students = await self.student_repo.get_by_class(class_id)
        exams = await self.exam_repo.get_by_class(class_id)

        return {
            "class": {
                "id": class_.id,
                "name": class_.name,
                "grade": class_.grade,
                "teacher_id": class_.teacher_id,
                "academic_year": class_.academic_year,
                "semester": class_.semester,
                "created_at": class_.created_at,
            },
            "students": [
                {
                    "id": s.id,
                    "user_id": s.user_id,
                    "student_number": s.student_number,
                    "enrollment_year": s.enrollment_year,
                }
                for s in students
            ],
            "exams": [
                {
                    "id": e.id,
                    "title": e.title,
                    "exam_type": e.exam_type.value,
                    "status": e.status.value,
                    "exam_date": e.exam_date,
                }
                for e in exams
            ],
        }

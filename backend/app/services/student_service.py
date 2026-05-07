"""学生服务 — 负责学生信息创建、画像查询、知识雷达图及批量导入."""

from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.core.security import get_password_hash
from app.models.class_student import ClassStudent
from app.models.student import Student
from app.models.student_knowledge_state import MasteryStatus
from app.models.user import User, UserRole
from app.repositories.class_ import ClassRepository
from app.repositories.student import StudentRepository
from app.repositories.student_knowledge_state import StudentKnowledgeStateRepository
from app.repositories.user import UserRepository


class StudentService:
    """学生业务服务，编排学生相关的 Repository."""

    def __init__(self, session: AsyncSession) -> None:
        self.student_repo = StudentRepository(session)
        self.user_repo = UserRepository(session)
        self.class_repo = ClassRepository(session)
        self.knowledge_state_repo = StudentKnowledgeStateRepository(session)
        self.session = session

    async def create_student(self, data: dict) -> dict:
        """创建学生（含 User + Student 扩展信息 + 班级关联）.

        Args:
            data: 创建数据，需包含 username, email, password, student_number 等

        Returns:
            dict: 创建后的学生概要
        """
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        student_number = data.get("student_number")

        if not all([username, email, password, student_number]):
            raise BadRequestException(
                "username, email, password, student_number 为必填字段"
            )

        existing_user = await self.user_repo.get_by_username(username)
        if existing_user:
            raise BadRequestException(f"用户名 {username} 已存在")

        existing_student = await self.student_repo.get_by_student_number(
            student_number
        )
        if existing_student:
            raise BadRequestException(f"学号 {student_number} 已存在")

        user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            real_name=data.get("real_name"),
            role=UserRole.student,
            phone=data.get("phone"),
            avatar_url=data.get("avatar_url"),
        )
        created_user = await self.user_repo.create(user)

        student = Student(
            user_id=created_user.id,
            student_number=student_number,
            class_id=data.get("class_id"),
            enrollment_year=data.get("enrollment_year"),
        )
        created_student = await self.student_repo.create(student)

        if data.get("class_id"):
            class_ = await self.class_repo.get_by_id(data["class_id"])
            if not class_:
                raise NotFoundException(f"班级 {data['class_id']} 不存在")

            assoc = ClassStudent(
                class_id=class_.id, student_id=created_student.id
            )
            self.session.add(assoc)
            await self.session.commit()

        return {
            "student_id": created_student.id,
            "user_id": created_user.id,
            "username": created_user.username,
            "student_number": created_student.student_number,
            "class_id": created_student.class_id,
        }

    async def get_student_profile(self, student_id: int) -> dict:
        """获取学生基本信息 + 班级 + 知识状态概览.

        Args:
            student_id: 学生 ID

        Returns:
            dict: 学生画像
        """
        student = await self.student_repo.get_by_id(student_id)
        if not student:
            raise NotFoundException(f"学生 {student_id} 不存在")

        user = await self.user_repo.get_by_id(student.user_id)
        class_ = None
        if student.class_id:
            class_ = await self.class_repo.get_by_id(student.class_id)

        knowledge_states = await self.knowledge_state_repo.get_by_student(
            student_id
        )
        weak_count = sum(
            1 for s in knowledge_states if s.status == MasteryStatus.weak
        )
        mastered_count = sum(
            1 for s in knowledge_states if s.status == MasteryStatus.mastered
        )

        return {
            "student_id": student.id,
            "user_id": student.user_id,
            "username": user.username if user else None,
            "real_name": user.real_name if user else None,
            "student_number": student.student_number,
            "class": (
                {
                    "id": class_.id,
                    "name": class_.name,
                    "grade": class_.grade,
                }
                if class_
                else None
            ),
            "enrollment_year": student.enrollment_year,
            "knowledge_summary": {
                "total": len(knowledge_states),
                "mastered": mastered_count,
                "weak": weak_count,
                "normal": len(knowledge_states)
                - weak_count
                - mastered_count,
            },
        }

    async def get_student_knowledge_radar(self, student_id: int) -> dict:
        """获取所有知识状态，按学科分组，计算雷达图数据.

        Args:
            student_id: 学生 ID

        Returns:
            dict: 雷达图维度及数值
        """
        student = await self.student_repo.get_by_id(student_id)
        if not student:
            raise NotFoundException(f"学生 {student_id} 不存在")

        states = await self.knowledge_state_repo.get_by_student(student_id)
        # 按知识点所属学科分组计算平均掌握度
        subject_scores: dict[int, list[float]] = {}
        for state in states:
            # knowledge_point 关系在异步环境下可能未加载，
            # 这里使用 knowledge_point_id 作为分组键的兜底方案
            kp_id = state.knowledge_point_id
            subject_scores.setdefault(kp_id, []).append(
                state.mastery_probability
            )

        # 若需真正按 subject_id 分组，建议在上层通过 join 查询补充
        # 此处返回按知识点维度聚合的雷达数据
        dimensions = []
        for dim_id, scores in subject_scores.items():
            avg_score = sum(scores) / len(scores) if scores else 0.0
            dimensions.append(
                {
                    "knowledge_point_id": dim_id,
                    "avg_mastery": round(avg_score, 3),
                    "count": len(scores),
                }
            )

        return {
            "student_id": student_id,
            "dimensions": dimensions,
        }

    async def batch_import_students(
        self, class_id: int, students_data: list[dict]
    ) -> dict:
        """批量导入学生（从 Excel/JSON 解析后的数据）.

        Service 层控制事务：全部成功或全部回滚（除已捕获的业务错误外）.

        Args:
            class_id: 目标班级 ID
            students_data: 学生数据列表

        Returns:
            dict: 导入结果统计
        """
        class_ = await self.class_repo.get_by_id(class_id)
        if not class_:
            raise NotFoundException(f"班级 {class_id} 不存在")

        created_count = 0
        errors = []

        for idx, item in enumerate(students_data):
            try:
                username = item.get("username")
                email = item.get("email")
                password = item.get("password", "123456")
                student_number = item.get("student_number")

                if not all([username, email, student_number]):
                    errors.append(
                        {"index": idx, "reason": "缺少必填字段"}
                    )
                    continue

                existing = await self.user_repo.get_by_username(username)
                if existing:
                    errors.append(
                        {
                            "index": idx,
                            "reason": f"用户名 {username} 已存在",
                        }
                    )
                    continue

                user = User(
                    username=username,
                    email=email,
                    hashed_password=get_password_hash(password),
                    real_name=item.get("real_name"),
                    role=UserRole.student,
                    phone=item.get("phone"),
                )
                self.session.add(user)
                await self.session.flush()

                student = Student(
                    user_id=user.id,
                    student_number=student_number,
                    class_id=class_id,
                    enrollment_year=item.get("enrollment_year"),
                )
                self.session.add(student)
                await self.session.flush()

                assoc = ClassStudent(
                    class_id=class_id, student_id=student.id
                )
                self.session.add(assoc)

                created_count += 1
            except Exception as exc:
                errors.append({"index": idx, "reason": str(exc)})

        await self.session.commit()

        return {
            "class_id": class_id,
            "created_count": created_count,
            "error_count": len(errors),
            "errors": errors,
        }

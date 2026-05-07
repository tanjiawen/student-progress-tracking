"""
学科跟踪引擎 - 学生知识状态更新
实现 BKT（贝叶斯知识追踪）简化变体 + ELO 变体 + 时间衰减
"""

from datetime import UTC, datetime


class KnowledgeState:
    """单个知识点的掌握状态"""

    def __init__(
        self,
        student_id: int = 0,
        knowledge_point_id: int = 0,
        mastery_probability: float = 0.5,
        total_attempts: int = 0,
        correct_count: int = 0,
        consecutive_correct: int = 0,
        last_error_type: str | None = None,
        last_graded_at: datetime | None = None,
    ):
        self.student_id = student_id
        self.knowledge_point_id = knowledge_point_id
        self.mastery_probability = mastery_probability
        self.total_attempts = total_attempts
        self.correct_count = correct_count
        self.consecutive_correct = consecutive_correct
        self.last_error_type = last_error_type
        self.last_graded_at = last_graded_at

    def to_dict(self) -> dict:
        return {
            "student_id": self.student_id,
            "knowledge_point_id": self.knowledge_point_id,
            "mastery_probability": round(self.mastery_probability, 4),
            "decayed_mastery": round(self.get_decayed_mastery(), 4),
            "total_attempts": self.total_attempts,
            "correct_count": self.correct_count,
            "consecutive_correct": self.consecutive_correct,
            "last_error_type": self.last_error_type,
            "last_graded_at": self.last_graded_at.isoformat() if self.last_graded_at else None,
            "status": self.get_status(),
        }

    def get_decayed_mastery(self, half_life_days: int = 30) -> float:
        """计算时间衰减后的掌握度"""
        if not self.last_graded_at:
            return self.mastery_probability

        days_passed = (datetime.now(UTC) - self.last_graded_at).total_seconds() / 86400
        decay = 0.5 ** (days_passed / half_life_days)
        return self.mastery_probability * decay

    def get_status(self) -> str:
        """掌握状态分级"""
        decayed = self.get_decayed_mastery()
        if decayed >= 0.8:
            return "mastered"
        elif decayed >= 0.4:
            return "normal"
        return "weak"


class KnowledgeTracker:
    """
    学科跟踪引擎

    算法参数：
    - P(L0): 初始掌握概率 = 0.5
    - P(T): 学习转移概率 = 0.3（答对后从未掌握到掌握的转移）
    - P(S): 失误概率 = 0.1（掌握后答错的概率）
    - P(G): 猜测概率 = 0.2（未掌握但猜对的概率）
    - 时间衰减半衰期: 30 天
    """

    # BKT 参数
    P_T = 0.30  # 学习转移概率
    P_S = 0.10  # 失误概率
    P_G = 0.20  # 猜测概率
    P_L0 = 0.50  # 初始掌握概率

    # ELO 参数
    ELO_K = 32  # 更新系数
    ELO_BASE = 1500  # 基础分

    def __init__(self):
        # 内存中的状态缓存（实际应持久化到数据库）
        self._states: dict[tuple[int, int], KnowledgeState] = {}

    def get_state(
        self,
        student_id: int,
        knowledge_point_id: int,
    ) -> KnowledgeState:
        """获取学生某知识点的状态"""
        key = (student_id, knowledge_point_id)
        if key not in self._states:
            self._states[key] = KnowledgeState(
                student_id=student_id,
                knowledge_point_id=knowledge_point_id,
                mastery_probability=self.P_L0,
            )
        return self._states[key]

    def update_from_grading(
        self,
        student_id: int,
        knowledge_point_id: int,
        is_correct: bool,
        error_type: str | None = None,
        question_difficulty: float = 1.0,
    ) -> KnowledgeState:
        """
        根据判卷结果更新知识状态

        Args:
            student_id: 学生 ID
            knowledge_point_id: 知识点 ID
            is_correct: 是否答对
            error_type: 错误类型
            question_difficulty: 题目难度 (1.0-5.0)

        Returns:
            更新后的 KnowledgeState
        """
        state = self.get_state(student_id, knowledge_point_id)

        # 1. BKT 更新
        p_l = state.mastery_probability

        if is_correct:
            # P(L|Correct) = P(Correct|L) * P(L) / P(Correct)
            p_correct = p_l * (1 - self.P_S) + (1 - p_l) * self.P_G
            p_l_new = (p_l * (1 - self.P_S)) / p_correct if p_correct > 0 else p_l
        else:
            # P(L|Incorrect) = P(Incorrect|L) * P(L) / P(Incorrect)
            p_incorrect = p_l * self.P_S + (1 - p_l) * (1 - self.P_G)
            p_l_new = (p_l * self.P_S) / p_incorrect if p_incorrect > 0 else p_l

        # 2. 学习转移（答对后额外提升）
        if is_correct:
            p_l_new = p_l_new + (1 - p_l_new) * self.P_T

        # 3. ELO 风格调整（根据题目难度）
        # 难题答对提升更多，简单题答错下降更多
        difficulty_factor = (question_difficulty - 1) / 4.0  # 0-1
        if is_correct:
            boost = 0.05 * (1 + difficulty_factor)
            p_l_new = min(1.0, p_l_new + boost)
        else:
            penalty = 0.06 * (1 + (1 - difficulty_factor))
            p_l_new = max(0.15, p_l_new - penalty)  # 设置下限，避免完全归零

        # 更新状态
        state.mastery_probability = round(p_l_new, 4)
        state.total_attempts += 1
        if is_correct:
            state.correct_count += 1
            state.consecutive_correct += 1
        else:
            state.consecutive_correct = 0
            state.last_error_type = error_type

        state.last_graded_at = datetime.now(UTC)

        return state

    def batch_update(
        self,
        student_id: int,
        results: list[dict],
    ) -> list[KnowledgeState]:
        """
        批量更新（一次考试后批量处理）

        Args:
            results: [
                {
                    "knowledge_point_id": 1,
                    "is_correct": True/False,
                    "error_type": "...",
                    "question_difficulty": 3.0
                }
            ]
        """
        updated = []
        for result in results:
            state = self.update_from_grading(
                student_id=student_id,
                knowledge_point_id=result["knowledge_point_id"],
                is_correct=result["is_correct"],
                error_type=result.get("error_type"),
                question_difficulty=result.get("question_difficulty", 1.0),
            )
            updated.append(state)
        return updated

    def get_weak_points(
        self,
        student_id: int,
        top_k: int = 5,
        subject_id: int | None = None,
    ) -> list[dict]:
        """
        获取学生的薄弱知识点

        Returns:
            [{
                "knowledge_point_id": 1,
                "mastery_probability": 0.35,
                "decayed_mastery": 0.28,
                "total_attempts": 12,
                "correct_rate": 0.33,
                "status": "weak",
                "last_error_type": "calculation_error"
            }]
        """
        student_states = [
            state for key, state in self._states.items()
            if key[0] == student_id
        ]

        # 按掌握度排序（低的在前）
        student_states.sort(key=lambda s: s.get_decayed_mastery())

        weak_points = []
        for state in student_states[:top_k]:
            if state.get_status() == "weak":
                weak_points.append({
                    "knowledge_point_id": state.knowledge_point_id,
                    "mastery_probability": state.mastery_probability,
                    "decayed_mastery": state.get_decayed_mastery(),
                    "total_attempts": state.total_attempts,
                    "correct_rate": round(state.correct_count / max(state.total_attempts, 1), 2),
                    "status": state.get_status(),
                    "last_error_type": state.last_error_type,
                    "consecutive_correct": state.consecutive_correct,
                })

        return weak_points

    def get_radar_data(
        self,
        student_id: int,
        dimension_kps: dict[str, list[int]],
    ) -> list[dict]:
        """
        获取雷达图数据

        Args:
            dimension_kps: {"函数与方程": [1,2,3], "几何": [4,5,6]}

        Returns:
            [{"name": "函数与方程", "mastery": 0.72}, ...]
        """
        radar = []
        for name, kp_ids in dimension_kps.items():
            scores = []
            for kp_id in kp_ids:
                state = self.get_state(student_id, kp_id)
                scores.append(state.get_decayed_mastery())

            avg_mastery = sum(scores) / len(scores) if scores else 0.0
            radar.append({
                "name": name,
                "mastery": round(avg_mastery, 2),
            })

        return radar

    def get_mastery_trend(
        self,
        student_id: int,
        knowledge_point_id: int,
        history: list[dict],
    ) -> list[dict]:
        """
        计算某知识点的掌握度变化趋势

        Args:
            history: [{"date": "2026-04-01", "is_correct": True}, ...]
        """
        trend = []
        current_p = self.P_L0

        for record in history:
            is_correct = record["is_correct"]
            if is_correct:
                p_correct = current_p * (1 - self.P_S) + (1 - current_p) * self.P_G
                current_p = (current_p * (1 - self.P_S)) / p_correct if p_correct > 0 else current_p
                current_p = current_p + (1 - current_p) * self.P_T
            else:
                p_incorrect = current_p * self.P_S + (1 - current_p) * (1 - self.P_G)
                current_p = (current_p * self.P_S) / p_incorrect if p_incorrect > 0 else current_p

            current_p = max(0.0, min(1.0, current_p))
            trend.append({
                "date": record["date"],
                "mastery": round(current_p, 4),
                "is_correct": is_correct,
            })

        return trend

    def calculate_class_heatmap(
        self,
        student_ids: list[int],
        knowledge_point_ids: list[int],
    ) -> list[dict]:
        """
        计算班级薄弱知识点热力图

        Returns:
            [{
                "knowledge_point_id": 1,
                "name": "顶点坐标",
                "class_mastery_avg": 0.45,
                "student_count_below_0.5": 28,
                "color": "#ff4d4f"
            }]
        """
        heatmap = []

        for kp_id in knowledge_point_ids:
            scores = []
            weak_count = 0

            for sid in student_ids:
                state = self.get_state(sid, kp_id)
                decayed = state.get_decayed_mastery()
                scores.append(decayed)
                if decayed < 0.5:
                    weak_count += 1

            avg_mastery = sum(scores) / len(scores) if scores else 0.0

            # 颜色映射
            if avg_mastery < 0.4:
                color = "#ff4d4f"  # 红色 - 薄弱
            elif avg_mastery < 0.6:
                color = "#faad14"  # 橙色 - 一般
            elif avg_mastery < 0.8:
                color = "#52c41a"  # 绿色 - 良好
            else:
                color = "#1890ff"  # 蓝色 - 优秀

            heatmap.append({
                "knowledge_point_id": kp_id,
                "class_mastery_avg": round(avg_mastery, 2),
                "student_count_below_0.5": weak_count,
                "total_students": len(student_ids),
                "weak_ratio": round(weak_count / max(len(student_ids), 1), 2),
                "color": color,
            })

        # 按薄弱比例排序
        heatmap.sort(key=lambda x: x["weak_ratio"], reverse=True)
        return heatmap


# 全局实例
knowledge_tracker = KnowledgeTracker()

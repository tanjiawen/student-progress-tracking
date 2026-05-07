from __future__ import annotations

from datetime import UTC, datetime


class SpacedRepetition:
    """基于 SM-2 算法的间隔重复调度器."""

    # SM-2 默认参数
    DEFAULT_EASINESS_FACTOR: float = 2.5
    MIN_EASINESS_FACTOR: float = 1.3
    MAX_QUALITY: int = 5

    def calculate_next_review(
        self,
        quality: int,
        repetition_count: int,
        easiness_factor: float,
        interval_days: int,
    ) -> tuple[int, float, int]:
        """计算下一次复习时间.

        Args:
            quality: 答题质量（0-5），5 表示完美回答，0 表示完全不会
            repetition_count: 已经连续成功复习的次数
            easiness_factor: 当前易度因子
            interval_days: 当前间隔天数

        Returns:
            (新间隔天数, 新 EF, 新重复次数)
        """
        quality = max(0, min(self.MAX_QUALITY, quality))

        if quality < 3:
            # 回答质量差，重置重复次数，间隔设为 1 天
            new_repetition = 0
            new_interval = 1
            # EF 保持不变或轻微下降
            new_ef = max(
                self.MIN_EASINESS_FACTOR,
                easiness_factor - 0.2,
            )
            return new_interval, round(new_ef, 2), new_repetition

        # 回答质量合格
        new_repetition = repetition_count + 1

        if new_repetition == 1:
            new_interval = 1
        elif new_repetition == 2:
            new_interval = 6
        else:
            new_interval = int(round(interval_days * easiness_factor))

        # 更新易度因子
        new_ef = easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        new_ef = max(self.MIN_EASINESS_FACTOR, new_ef)

        return new_interval, round(new_ef, 2), new_repetition

    def is_due(self, next_review_at: datetime | None) -> bool:
        """检查是否到期复习."""
        if next_review_at is None:
            return True
        return datetime.now(UTC) >= next_review_at

    def calculate_initial_review(self, quality: int) -> tuple[int, float, int]:
        """计算首次复习参数."""
        return self.calculate_next_review(
            quality=quality,
            repetition_count=0,
            easiness_factor=self.DEFAULT_EASINESS_FACTOR,
            interval_days=0,
        )

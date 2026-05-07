from __future__ import annotations

import json
import logging
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.ai.gateway import LLMGateway, LLMMessage, LLMRequest
from app.models.knowledge_point import KnowledgePoint
from app.models.question_template import QuestionTemplate
from app.repositories.knowledge_point import KnowledgePointRepository
from app.repositories.question_template import QuestionTemplateRepository
from app.services.question_vector_service import QuestionVectorService

logger = logging.getLogger(__name__)


class ExerciseGenerator:
    """AI 出题引擎."""

    MAX_RETRIES: int = 3

    def __init__(self, session: AsyncSession):
        self.session = session
        self.question_repo = QuestionTemplateRepository(session)
        self.kp_repo = KnowledgePointRepository(session)
        self.vector_service = QuestionVectorService()
        self.gateway = LLMGateway()

    async def generate_exercise(
        self,
        student_id: int,
        target_knowledge_point_ids: list[int],
        target_error_types: list[str] | None = None,
        difficulty_range: tuple[int, int] = (1, 5),
        question_count: int = 10,
    ) -> dict[str, Any]:
        """生成练习卷.

        策略:
        1. 从题库检索目标知识点的现有题目（RAG）
        2. 如果题目不足，用 LLM 生成新题
        3. 组装练习卷：基础巩固 40% + 变式提升 40% + 综合应用 20%
        4. 每题生成标准答案和 AI 解析
        """
        target_error_types = target_error_types or []
        min_diff, max_diff = difficulty_range

        # 1. 检索相似题
        retrieved: list[QuestionTemplate] = []
        for kp_id in target_knowledge_point_ids:
            items = await self._retrieve_similar_questions(kp_id, limit=5)
            for item in items:
                if item not in retrieved:
                    retrieved.append(item)
            if len(retrieved) >= question_count * 2:
                break

        # 2. 获取知识点信息
        knowledge_points: list[KnowledgePoint] = []
        for kp_id in target_knowledge_point_ids:
            kp = await self.kp_repo.get_by_id(kp_id)
            if kp:
                knowledge_points.append(kp)

        # 3. 计算各层级题目数量
        base_count = max(1, int(question_count * 0.4))
        variant_count = max(1, int(question_count * 0.4))
        advanced_count = question_count - base_count - variant_count

        questions: list[dict[str, Any]] = []
        used_template_ids: set[int | None] = set()

        # 先从检索到的题目中挑选
        def pick_from_retrieved(diff_low: int, diff_high: int, count: int) -> list[dict[str, Any]]:
            result: list[dict[str, Any]] = []
            for qt in retrieved:
                if qt.id in used_template_ids:
                    continue
                if diff_low <= qt.difficulty <= diff_high:
                    result.append(self._template_to_dict(qt))
                    used_template_ids.add(qt.id)
                if len(result) >= count:
                    break
            return result

        # 基础巩固（难度较低）
        base_mid = (min_diff + max_diff) // 2
        base_diff_low, base_diff_high = min_diff, max(base_mid - 1, min_diff)
        questions.extend(pick_from_retrieved(base_diff_low, base_diff_high, base_count))

        # 变式提升（中等难度）
        var_diff_low, var_diff_high = base_diff_low + 1, max_diff - 1
        questions.extend(pick_from_retrieved(var_diff_low, var_diff_high, variant_count))

        # 综合应用（高难度）
        adv_diff_low, adv_diff_high = max_diff - 1, max_diff
        questions.extend(pick_from_retrieved(adv_diff_low, adv_diff_high, advanced_count))

        # 4. 如果题目不足，用 LLM 生成新题
        missing = question_count - len(questions)
        if missing > 0:
            logger.info("题目不足，需要生成 %s 道新题", missing)
            generated = await self._generate_missing_questions(
                knowledge_points=knowledge_points,
                target_error_types=target_error_types,
                difficulty_range=difficulty_range,
                count=missing,
                existing_questions=questions,
            )
            questions.extend(generated)

        # 5. 按策略组装
        exercise_data = await self._assemble_exercise(
            questions=questions,
            strategy={
                "base_count": base_count,
                "variant_count": variant_count,
                "advanced_count": advanced_count,
                "difficulty_range": difficulty_range,
            },
        )

        await self.gateway.close()
        return exercise_data

    async def _retrieve_similar_questions(
        self,
        kp_id: int,
        limit: int = 5,
    ) -> list[QuestionTemplate]:
        """从 Qdrant 检索相似题作为候选."""
        try:
            results = await self.vector_service.search_by_knowledge_point(
                kp_id=kp_id,
                limit=limit * 2,
            )
        except Exception as e:
            logger.warning("Qdrant 检索失败，fallback 到数据库: %s", e)
            return await self.question_repo.get_by_knowledge_point(kp_id)

        templates: list[QuestionTemplate] = []
        seen_ids: set[int] = set()
        for res in results:
            qid = res.get("payload", {}).get("question_id")
            if qid and qid not in seen_ids:
                qt = await self.question_repo.get_by_id(qid)
                if qt:
                    templates.append(qt)
                    seen_ids.add(qid)
            if len(templates) >= limit:
                break

        # 如果向量检索结果不足，补充数据库查询
        if len(templates) < limit:
            db_items = await self.question_repo.get_by_knowledge_point(kp_id)
            for item in db_items:
                if item.id not in seen_ids:
                    templates.append(item)
                    seen_ids.add(item.id)
                if len(templates) >= limit:
                    break

        return templates

    async def _generate_missing_questions(
        self,
        knowledge_points: list[KnowledgePoint],
        target_error_types: list[str],
        difficulty_range: tuple[int, int],
        count: int,
        existing_questions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """生成缺失的题目."""
        generated: list[dict[str, Any]] = []
        few_shot = existing_questions[:3] if existing_questions else []

        for i in range(count):
            kp = knowledge_points[i % len(knowledge_points)] if knowledge_points else None
            error_type = target_error_types[i % len(target_error_types)] if target_error_types else None
            difficulty = min(
                difficulty_range[0] + (i % (difficulty_range[1] - difficulty_range[0] + 1)),
                difficulty_range[1],
            )

            for attempt in range(self.MAX_RETRIES):
                try:
                    question = await self._generate_new_question(
                        knowledge_point=kp,
                        error_type=error_type,
                        difficulty=difficulty,
                        few_shot_examples=few_shot,
                    )
                except Exception as e:
                    logger.warning("题目生成失败 (attempt %s): %s", attempt + 1, e)
                    continue

                # 答案自验证
                verified = await self._verify_answer(
                    question=question,
                    answer=question.get("standard_answer", ""),
                )
                if verified.get("status") == "needs_review":
                    question["needs_review"] = True
                    logger.warning("题目答案验证不一致，标记为 needs_review")

                generated.append(question)
                few_shot.append(question)
                break
            else:
                logger.error("题目生成重试 %s 次后仍失败，跳过", self.MAX_RETRIES)

        return generated

    async def _generate_new_question(
        self,
        knowledge_point: KnowledgePoint | None,
        error_type: str | None,
        difficulty: int,
        few_shot_examples: list[dict],
    ) -> dict[str, Any]:
        """调用 LLM 生成新题."""
        kp_name = knowledge_point.name if knowledge_point else "综合知识点"
        kp_desc = knowledge_point.description or "" if knowledge_point else ""

        few_shot_text = ""
        for idx, ex in enumerate(few_shot_examples[:3], 1):
            few_shot_text += f"""
示例 {idx}:
题干: {ex.get('content', '')}
选项: {ex.get('options', '无')}
答案: {ex.get('standard_answer', '')}
解析: {ex.get('ai_explanation', ex.get('explanation', ''))}
"""

        prompt = f"""你是一位资深学科教师，请根据以下信息生成一道高质量的练习题。

## 知识点
名称: {kp_name}
描述: {kp_desc}

## 难度
{difficulty}/5（1 最简单，5 最难）

## 目标错因类型
{error_type or "一般性考查"}

## Few-shot 示例
{few_shot_text}

## 输出格式（严格 JSON）
{{
    "content": "题干文本，支持 LaTeX",
    "content_latex": "题干 LaTeX（如有）",
    "options": {{"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"}},
    "standard_answer": "标准答案",
    "explanation": "详细解析",
    "scoring_criteria": "评分细则",
    "difficulty": {difficulty},
    "knowledge_point_ids": {json.dumps([knowledge_point.id] if knowledge_point else [])},
    "question_type": "choice"
}}

注意：
1. 只输出 JSON，不要有任何其他文字
2. 难度为 {difficulty}，请确保题目与该难度匹配
3. 选项字段仅在选择题中出现，其他题型可为 null
4. 数学公式使用 LaTeX 格式
"""

        request = LLMRequest(
            messages=[
                LLMMessage(
                    role="system",
                    content="你是一位资深学科教师，擅长根据知识点生成针对性练习题。只输出严格 JSON 格式。",
                ),
                LLMMessage(role="user", content=prompt),
            ],
            model="deepseek-chat",
            max_tokens=4096,
            temperature=0.5,
        )

        response = await self.gateway.chat(request, preferred_provider="deepseek")
        content = self._clean_json(response.content)

        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("LLM 输出不是有效的 JSON 对象")

        return parsed

    async def _verify_answer(
        self,
        question: dict[str, Any],
        answer: str,
    ) -> dict[str, Any]:
        """答案自验证：独立调用 LLM 求解，与生成答案对比."""
        content = question.get("content", "")
        options = question.get("options")
        options_text = ""
        if options:
            if isinstance(options, dict):
                options_text = "\n".join(f"{k}: {v}" for k, v in options.items())
            elif isinstance(options, list):
                options_text = "\n".join(str(o) for o in options)

        prompt = f"""请独立求解以下题目，并给出答案。

## 题目
{content}
{options_text}

## 要求
只输出答案，不要解释。如果选择题只输出选项字母（如 A）。
"""

        request = LLMRequest(
            messages=[
                LLMMessage(role="system", content="你是一位严谨的解题专家，请只输出最终答案。"),
                LLMMessage(role="user", content=prompt),
            ],
            model="deepseek-chat",
            max_tokens=1024,
            temperature=0.2,
        )

        try:
            response = await self.gateway.chat(request, preferred_provider="deepseek")
            generated_answer = answer.strip().lower()
            verified_answer = response.content.strip().lower()

            # 简单比较
            match = generated_answer == verified_answer
            if not match:
                # 尝试更宽松的比较
                match = generated_answer in verified_answer or verified_answer in generated_answer

            if match:
                return {"status": "verified", "verified_answer": verified_answer}
            return {
                "status": "needs_review",
                "generated_answer": generated_answer,
                "verified_answer": verified_answer,
            }
        except Exception as e:
            logger.warning("答案验证失败: %s", e)
            return {"status": "needs_review", "reason": str(e)}

    async def _assemble_exercise(
        self,
        questions: list[dict[str, Any]],
        strategy: dict[str, Any],
    ) -> dict[str, Any]:
        """按策略组装练习卷."""
        # 按难度排序：基础 -> 变式 -> 综合
        def sort_key(q: dict[str, Any]) -> int:
            return q.get("difficulty", 3)

        sorted_questions = sorted(questions, key=sort_key)

        # 给每题分配 max_score
        for i, q in enumerate(sorted_questions):
            diff = q.get("difficulty", 3)
            # 简单题 5 分，中等 8 分，难题 10 分
            if diff <= 2:
                q["max_score"] = 5.0
            elif diff <= 4:
                q["max_score"] = 8.0
            else:
                q["max_score"] = 10.0
            q["sequence_number"] = i + 1

        total_score = sum(q.get("max_score", 0) for q in sorted_questions)

        return {
            "questions": sorted_questions,
            "strategy": strategy,
            "total_questions": len(sorted_questions),
            "total_score": total_score,
        }

    @staticmethod
    def _template_to_dict(qt: QuestionTemplate) -> dict[str, Any]:
        """将 QuestionTemplate 转为 dict."""
        return {
            "content": qt.content,
            "content_latex": qt.content_latex,
            "options": qt.options,
            "standard_answer": qt.standard_answer or "",
            "explanation": "",
            "scoring_criteria": qt.scoring_criteria or "",
            "difficulty": qt.difficulty,
            "knowledge_point_ids": qt.knowledge_point_ids or [],
            "question_type": qt.question_type.value if hasattr(qt.question_type, "value") else str(qt.question_type),
            "question_template_id": qt.id,
        }

    @staticmethod
    def _clean_json(text: str) -> str:
        """清理 LLM 输出的 JSON 文本."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

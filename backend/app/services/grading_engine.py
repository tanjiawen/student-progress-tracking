"""
判卷评估引擎
支持客观题自动匹配 + 主观题 LLM 智能判分 + 错因分析 + 知识点映射
"""

import json
import re
from typing import Any

from app.ai.openai_vision import OpenAIVisionClient
from app.ai.qwen_vl import QwenVLClient
from app.core.config import settings


class GradingResult:
    """判卷结果"""

    def __init__(
        self,
        is_correct: bool = False,
        score: float = 0.0,
        max_score: float = 0.0,
        error_type: str | None = None,
        error_type_detail: str = "",
        knowledge_point_ids: list[int] | None = None,
        suggestion: str = "",
        confidence: float = 0.0,
        ai_model: str = "",
        raw_response: dict | None = None,
    ):
        self.is_correct = is_correct
        self.score = score
        self.max_score = max_score
        self.error_type = error_type
        self.error_type_detail = error_type_detail
        self.knowledge_point_ids = knowledge_point_ids or []
        self.suggestion = suggestion
        self.confidence = confidence
        self.ai_model = ai_model
        self.raw_response = raw_response or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_correct": self.is_correct,
            "score": self.score,
            "max_score": self.max_score,
            "error_type": self.error_type,
            "error_type_detail": self.error_type_detail,
            "knowledge_point_ids": self.knowledge_point_ids,
            "suggestion": self.suggestion,
            "confidence": self.confidence,
            "ai_model": self.ai_model,
        }


class GradingEngine:
    """判卷引擎"""

    # 错因类型定义
    ERROR_TYPES = {
        "correct": "回答正确",
        "concept_error": "概念不清",
        "calculation_error": "计算错误",
        "misreading": "审题偏差",
        "missing_step": "步骤遗漏",
        "logic_break": "逻辑断裂",
        "formula_error": "公式错误",
        "notation_error": "符号错误",
        "incomplete": "回答不完整",
        "unclear": "字迹不清无法识别",
        "unknown": "其他错误",
    }

    # 客观题类型（可直接匹配）
    OBJECTIVE_TYPES = {"choice", "fill_blank"}

    # 主观题类型（需要 LLM 判分）
    SUBJECTIVE_TYPES = {"short_answer", "calculation", "proof"}

    def __init__(self):
        self.qwen = QwenVLClient()
        self.gpt4v = OpenAIVisionClient()
        self.model = "deepseek-r1"  # 默认使用 DeepSeek 进行判卷推理

    async def grade(
        self,
        question_type: str,
        question_content: str,
        standard_answer: str,
        student_answer: str,
        max_score: float = 0.0,
        knowledge_point_hints: list[str] | None = None,
        use_llm_for_objective: bool = False,
    ) -> GradingResult:
        """
        统一判卷入口

        Args:
            question_type: 题型
            question_content: 题目内容
            standard_answer: 标准答案
            student_answer: 学生答案
            max_score: 满分
            knowledge_point_hints: 知识点提示
            use_llm_for_objective: 客观题是否也用 LLM（更严格但 slower）

        Returns:
            GradingResult
        """
        if question_type in self.OBJECTIVE_TYPES and not use_llm_for_objective:
            return self._grade_objective(
                question_type=question_type,
                standard_answer=standard_answer,
                student_answer=student_answer,
                max_score=max_score,
            )
        else:
            return await self._grade_subjective(
                question_type=question_type,
                question_content=question_content,
                standard_answer=standard_answer,
                student_answer=student_answer,
                max_score=max_score,
                knowledge_point_hints=knowledge_point_hints,
            )

    def _grade_objective(
        self,
        question_type: str,
        standard_answer: str,
        student_answer: str,
        max_score: float,
    ) -> GradingResult:
        """客观题自动匹配判分"""
        if not student_answer or not student_answer.strip():
            return GradingResult(
                is_correct=False,
                score=0.0,
                max_score=max_score,
                error_type="incomplete",
                error_type_detail="未作答",
                confidence=1.0,
                ai_model="rule-based",
            )

        std = self._normalize_answer(standard_answer)
        stu = self._normalize_answer(student_answer)

        if question_type == "choice":
            is_correct = std == stu and len(stu) == 1
        else:
            # 填空题支持多种等价形式
            is_correct = self._answers_equivalent(std, stu)

        if is_correct:
            return GradingResult(
                is_correct=True,
                score=max_score,
                max_score=max_score,
                error_type="correct",
                error_type_detail="回答正确",
                confidence=1.0,
                ai_model="rule-based",
            )
        else:
            error_type = self._infer_objective_error_type(std, stu)
            return GradingResult(
                is_correct=False,
                score=0.0,
                max_score=max_score,
                error_type=error_type,
                error_type_detail=f"标准答案: {standard_answer}, 学生答案: {student_answer}",
                confidence=1.0,
                ai_model="rule-based",
            )

    async def _grade_subjective(
        self,
        question_type: str,
        question_content: str,
        standard_answer: str,
        student_answer: str,
        max_score: float,
        knowledge_point_hints: list[str] | None = None,
    ) -> GradingResult:
        """主观题 LLM 智能判分"""
        if not student_answer or not student_answer.strip():
            return GradingResult(
                is_correct=False,
                score=0.0,
                max_score=max_score,
                error_type="incomplete",
                error_type_detail="未作答",
                confidence=1.0,
                ai_model=self.model,
            )

        prompt = self._build_grading_prompt(
            question_type=question_type,
            question_content=question_content,
            standard_answer=standard_answer,
            student_answer=student_answer,
            max_score=max_score,
            knowledge_point_hints=knowledge_point_hints,
        )

        try:
            # 调用 LLM（使用 DeepSeek API 通过 OpenAI 兼容接口）
            response = await self._call_llm(prompt)
            parsed = self._parse_grading_response(response)

            return GradingResult(
                is_correct=parsed.get("is_correct", False),
                score=float(parsed.get("score", 0)),
                max_score=max_score,
                error_type=parsed.get("error_type", "unknown"),
                error_type_detail=parsed.get("error_detail", ""),
                knowledge_point_ids=parsed.get("knowledge_points", []),
                suggestion=parsed.get("suggestion", ""),
                confidence=float(parsed.get("confidence", 0.8)),
                ai_model=self.model,
                raw_response={"prompt": prompt, "response": response, "parsed": parsed},
            )

        except Exception as e:
            # LLM 失败时保守给分，标记人工审核
            return GradingResult(
                is_correct=False,
                score=0.0,
                max_score=max_score,
                error_type="unknown",
                error_type_detail=f"AI 判卷失败: {str(e)}",
                confidence=0.0,
                ai_model=self.model,
            )

    async def grade_with_image(
        self,
        question_type: str,
        question_content: str,
        standard_answer: str,
        answer_image_bytes: bytes,
        max_score: float = 0.0,
        knowledge_point_hints: list[str] | None = None,
    ) -> GradingResult:
        """
        基于图片的手写作答判卷（多模态）
        """
        # 先 OCR 识别手写内容
        from app.ai.ocr_engine import ocr_engine

        ocr_result = await ocr_engine.recognize_student_answer(
            image_bytes=answer_image_bytes,
            question_content=question_content,
        )
        student_answer = ocr_result.get("text", "")

        # 再调用判卷
        result = await self.grade(
            question_type=question_type,
            question_content=question_content,
            standard_answer=standard_answer,
            student_answer=student_answer,
            max_score=max_score,
            knowledge_point_hints=knowledge_point_hints,
        )

        # 补充 OCR 信息
        if not result.raw_response:
            result.raw_response = {}
        result.raw_response["ocr_result"] = ocr_result

        return result

    def _build_grading_prompt(
        self,
        question_type: str,
        question_content: str,
        standard_answer: str,
        student_answer: str,
        max_score: float,
        knowledge_point_hints: list[str] | None = None,
    ) -> str:
        """构建判卷 Prompt"""
        kp_hint = ""
        if knowledge_point_hints:
            kp_hint = f"涉及知识点: {', '.join(knowledge_point_hints)}\n"

        return f"""你是一位严格的{question_type}判卷专家。请根据题目、标准答案和学生答案进行判分。

## 题目
{question_content}

## 标准答案
{standard_answer}

## 学生答案
{student_answer}

## 判分标准
- 满分: {max_score} 分
- 如果完全正确，给满分
- 如果部分正确，按步骤给分
- 如果完全错误，给 0 分
- 如果未作答或完全无法理解，给 0 分

{kp_hint}
## 输出格式（严格 JSON）
{{
    "is_correct": true/false,
    "score": 0.0,
    "error_type": "correct/concept_error/calculation_error/misreading/missing_step/logic_break/formula_error/notation_error/incomplete/unknown",
    "error_detail": "详细错因分析",
    "knowledge_points": ["知识点1", "知识点2"],
    "suggestion": "给学生的学习建议",
    "confidence": 0.95
}}

注意：
1. 只输出 JSON，不要有其他文字
2. confidence 表示你对判分结果的置信度（0-1）
3. 数学公式用 LaTeX 表示
"""

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        import httpx

        api_key = settings.DEEPSEEK_API_KEY or settings.OPENAI_API_KEY or ""
        base_url = settings.DEEPSEEK_BASE_URL or "https://api.deepseek.com/v1"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一位专业的学科判卷专家，擅长数学、物理等理科题目的评分。输出严格的 JSON 格式。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 2048,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    @staticmethod
    def _parse_grading_response(text: str) -> dict[str, Any]:
        """解析 LLM 判卷输出"""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        parsed = json.loads(text)

        # 验证必要字段
        if "is_correct" not in parsed:
            parsed["is_correct"] = float(parsed.get("score", 0)) > 0

        return parsed

    @staticmethod
    def _normalize_answer(answer: str) -> str:
        """标准化答案文本"""
        if not answer:
            return ""
        answer = answer.strip().upper()
        # 移除多余空格和标点
        answer = re.sub(r"\s+", "", answer)
        answer = answer.replace("．", ".")
        return answer

    @staticmethod
    def _answers_equivalent(a: str, b: str) -> bool:
        """判断两个答案是否等价（支持数学表达式简化）"""
        if a == b:
            return True

        # 尝试数值比较（如 "1/2" 和 "0.5"）
        try:
            from fractions import Fraction

            fa = Fraction(a)
            fb = Fraction(b)
            return abs(float(fa) - float(fb)) < 1e-6
        except Exception:
            pass

        # 数值直接比较
        try:
            return abs(float(a) - float(b)) < 1e-6
        except ValueError:
            pass

        return False

    @staticmethod
    def _infer_objective_error_type(std: str, stu: str) -> str:
        """推断客观题错误类型"""
        if not stu:
            return "incomplete"

        # 尝试数值比较
        try:
            from fractions import Fraction

            fs = Fraction(stu)
            fd = Fraction(std)
            if abs(float(fs) - float(fd)) < 1e-3:
                return "notation_error"  # 数值接近但格式不对
            return "calculation_error"
        except Exception:
            pass

        # 如果是选择题
        if len(stu) == 1 and stu.isalpha():
            return "concept_error"

        return "unknown"


# 全局实例
grading_engine = GradingEngine()

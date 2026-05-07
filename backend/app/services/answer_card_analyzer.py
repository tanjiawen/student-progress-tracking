"""
答题卡分析服务（方案B：结构化 OCR + DeepSeek 文本分析）

核心流程：
  1. 接收结构化 OCR 数据（人工预提取 / 高精度 OCR 模型提取）
  2. 调用 DeepSeek 进行学情深度分析
  3. 调用 DeepSeek 进行知识点掌握度评估
  4. 输出标准化 JSON 报告

使用方式：
  analyzer = AnswerCardAnalyzer()
  report = await analyzer.generate_full_report(structured_ocr_data)
"""

import json
from dataclasses import dataclass, field
from typing import Any

from app.ai.gateway import LLMGateway, LLMMessage, LLMRequest
from app.core.config import settings


@dataclass
class LearningAnalysisReport:
    """学情分析报告"""
    overall_evaluation: str = ""
    mastered_knowledge: list[str] = field(default_factory=list)
    weak_knowledge: list[str] = field(default_factory=list)
    error_patterns: list[dict[str, str]] = field(default_factory=list)
    short_term_suggestions: list[str] = field(default_factory=list)
    mid_term_suggestions: list[str] = field(default_factory=list)
    long_term_suggestions: list[str] = field(default_factory=list)
    next_exam_target: int = 0
    raw_content: str = ""
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_evaluation": self.overall_evaluation,
            "mastered_knowledge": self.mastered_knowledge,
            "weak_knowledge": self.weak_knowledge,
            "error_patterns": self.error_patterns,
            "short_term_suggestions": self.short_term_suggestions,
            "mid_term_suggestions": self.mid_term_suggestions,
            "long_term_suggestions": self.long_term_suggestions,
            "next_exam_target": self.next_exam_target,
            "model": self.model,
            "usage": self.usage,
        }


@dataclass
class KnowledgeMasteryItem:
    """单个知识点掌握度"""
    knowledge_point: str
    mastery_level: float
    confidence: float
    suggested_difficulty: str
    priority_review: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_point": self.knowledge_point,
            "mastery_level": self.mastery_level,
            "confidence": self.confidence,
            "suggested_difficulty": self.suggested_difficulty,
            "priority_review": self.priority_review,
        }


@dataclass
class AnswerCardReport:
    """答题卡完整分析报告"""
    student_info: dict[str, Any] = field(default_factory=dict)
    exam_info: dict[str, Any] = field(default_factory=dict)
    learning_analysis: LearningAnalysisReport | None = None
    knowledge_mastery: list[KnowledgeMasteryItem] = field(default_factory=list)
    raw_ocr_data: dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "student_info": self.student_info,
            "exam_info": self.exam_info,
            "learning_analysis": self.learning_analysis.to_dict() if self.learning_analysis else None,
            "knowledge_mastery": [k.to_dict() for k in self.knowledge_mastery],
            "raw_ocr_data": self.raw_ocr_data,
            "generated_at": self.generated_at,
        }


class AnswerCardAnalyzer:
    """答题卡分析服务"""

    def __init__(self):
        self.gateway = LLMGateway()

    async def analyze_learning_status(
        self,
        ocr_data: dict[str, Any],
        model: str | None = None,
    ) -> LearningAnalysisReport:
        """
        学情深度分析

        Args:
            ocr_data: 结构化 OCR 数据
            model: 指定模型（默认 deepseek-chat）

        Returns:
            LearningAnalysisReport
        """
        student = ocr_data.get("student_info", {})
        exam = ocr_data.get("exam_info", {})
        sections = ocr_data.get("sections", [])

        # 构建错题信息
        wrong_objective = []
        for sec in sections:
            for q in sec.get("questions", []):
                q_score = q.get("score")
                q_max = q.get("max_score", 0)
                # 如果题目本身没有 score，从子题汇总
                if q_score is None and q.get("sub_questions"):
                    q_score = sum(sq.get("score", 0) for sq in q["sub_questions"])
                    q_max = sum(sq.get("max_score", 0) for sq in q["sub_questions"])
                q_score = q_score or 0
                if q_score < q_max:
                    wrong_objective.append(
                        f"第{q['number']}题："
                        f"{'选 ' + q.get('student_answer', '?') + '，' if 'student_answer' in q else ''}"
                        f"失 {q_max - q_score} 分"
                    )

        subjective_issues = []
        for sec in sections:
            for q in sec.get("questions", []):
                for sq in q.get("sub_questions", []):
                    if sq.get("score", 0) < sq.get("max_score", 0):
                        subjective_issues.append({
                            "题号": f"{q['number']}{sq['sub_number']}",
                            "得分": f"{sq['score']}/{sq['max_score']}",
                            "问题": sq.get("issues", [sq.get("feedback", "")]),
                            "知识点": sq.get("knowledge_points", []),
                        })

        prompt = f"""你是一位资深初中道德与法治学科教师兼学情分析专家。请根据以下已结构化的答题卡数据，为学生生成一份详细的学情分析报告。

## 学生基本信息
- 姓名：{student.get('name', '未知')}
- 班级：{student.get('class', '未知')}
- 考试：{exam.get('title', '未知')}
- 学科：{exam.get('subject', '未知')}
- 总分：{exam.get('total_score', 0)} / {exam.get('max_score', 100)}（客观题 {exam.get('objective_score', 0)} 分，主观题 {exam.get('subjective_score', 0)} 分）

## 选择题错题
{chr(10).join(wrong_objective) if wrong_objective else '无（选择题全对）'}

## 主观题失分点
{json.dumps(subjective_issues, ensure_ascii=False, indent=2)}

## 输出要求
请严格按以下 JSON 格式输出，不要添加任何其他文字：
{{
  "overall_evaluation": "总体评价（100字左右）",
  "mastered_knowledge": ["已掌握的知识点1", "已掌握的知识点2"],
  "weak_knowledge": ["薄弱知识点1", "薄弱知识点2", "薄弱知识点3"],
  "error_patterns": [
    {{"type": "概念混淆", "description": "具体表现", "examples": ["题号"]}},
    {{"type": "表述不完整", "description": "具体表现", "examples": ["题号"]}}
  ],
  "short_term_suggestions": ["1周内措施1", "1周内措施2"],
  "mid_term_suggestions": ["1个月内措施1", "1个月内措施2"],
  "long_term_suggestions": ["长期习惯1", "长期习惯2"],
  "next_exam_target": 68
}}"""

        request = LLMRequest(
            messages=[
                LLMMessage(
                    role="system",
                    content="你是一位资深初中道德与法治教师，擅长学情分析和个性化教学建议。只输出 JSON，不要添加 markdown 代码块标记。",
                ),
                LLMMessage(role="user", content=prompt),
            ],
            model=model or "deepseek-chat",
            max_tokens=4096,
            temperature=0.3,
        )

        response = await self.gateway.chat(request, preferred_provider="deepseek")

        # 解析 JSON
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            # 兜底：返回原始内容
            parsed = {}

        return LearningAnalysisReport(
            overall_evaluation=parsed.get("overall_evaluation", ""),
            mastered_knowledge=parsed.get("mastered_knowledge", []),
            weak_knowledge=parsed.get("weak_knowledge", []),
            error_patterns=parsed.get("error_patterns", []),
            short_term_suggestions=parsed.get("short_term_suggestions", []),
            mid_term_suggestions=parsed.get("mid_term_suggestions", []),
            long_term_suggestions=parsed.get("long_term_suggestions", []),
            next_exam_target=parsed.get("next_exam_target", 0),
            raw_content=response.content,
            model=response.model,
            usage=response.usage,
        )

    async def assess_knowledge_mastery(
        self,
        ocr_data: dict[str, Any],
        model: str | None = None,
    ) -> list[KnowledgeMasteryItem]:
        """
        知识点掌握度评估

        Args:
            ocr_data: 结构化 OCR 数据
            model: 指定模型

        Returns:
            list[KnowledgeMasteryItem]
        """
        sections = ocr_data.get("sections", [])

        # 提取所有知识点及答题情况
        knowledge_items = []
        for sec in sections:
            for q in sec.get("questions", []):
                for sq in q.get("sub_questions", []):
                    for kp in sq.get("knowledge_points", []):
                        knowledge_items.append({
                            "knowledge_point": kp,
                            "question": f"{q['number']}{sq['sub_number']}",
                            "score": sq.get("score", 0),
                            "max_score": sq.get("max_score", 0),
                            "mastered": sq.get("score", 0) >= sq.get("max_score", 0),
                        })

        prompt = f"""你是一位教育数据分析师。请根据以下答题数据，为知识点追踪模型（BKT + ELO）生成分知识点掌握度评估。

## 答题数据
{json.dumps(knowledge_items, ensure_ascii=False, indent=2)}

## 输出要求
请严格按以下 JSON 数组格式输出，不要添加任何其他文字：
[
  {{
    "knowledge_point": "知识点名称",
    "mastery_level": 0.85,
    "confidence": 0.7,
    "suggested_difficulty": "medium",
    "priority_review": false
  }}
]

说明：
- mastery_level: 基于得分率估算（0-1），同一知识点多次出现时取平均
- confidence: 样本越多置信度越高（0-1）
- suggested_difficulty: easy / medium / hard
- priority_review: 掌握度低于0.6设为 true"""

        request = LLMRequest(
            messages=[
                LLMMessage(
                    role="system",
                    content="你是一位教育数据分析师，擅长将答题数据转化为知识点掌握度评估。只输出 JSON 数组，不要添加 markdown 代码块标记。",
                ),
                LLMMessage(role="user", content=prompt),
            ],
            model=model or "deepseek-chat",
            max_tokens=4096,
            temperature=0.1,
        )

        response = await self.gateway.chat(request, preferred_provider="deepseek")

        # 解析 JSON
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return []

        return [
            KnowledgeMasteryItem(
                knowledge_point=item.get("knowledge_point", ""),
                mastery_level=item.get("mastery_level", 0.0),
                confidence=item.get("confidence", 0.0),
                suggested_difficulty=item.get("suggested_difficulty", "medium"),
                priority_review=item.get("priority_review", False),
            )
            for item in parsed
        ]

    async def generate_full_report(
        self,
        ocr_data: dict[str, Any],
        model: str | None = None,
    ) -> AnswerCardReport:
        """
        生成完整分析报告

        Args:
            ocr_data: 结构化 OCR 数据
            model: 指定模型

        Returns:
            AnswerCardReport
        """
        from datetime import UTC, datetime

        learning_analysis = await self.analyze_learning_status(ocr_data, model)
        knowledge_mastery = await self.assess_knowledge_mastery(ocr_data, model)

        return AnswerCardReport(
            student_info=ocr_data.get("student_info", {}),
            exam_info=ocr_data.get("exam_info", {}),
            learning_analysis=learning_analysis,
            knowledge_mastery=knowledge_mastery,
            raw_ocr_data=ocr_data,
            generated_at=datetime.now(UTC).isoformat(),
        )

    async def close(self) -> None:
        """关闭连接"""
        await self.gateway.close()

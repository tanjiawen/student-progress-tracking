"""
版面分析引擎
将 OCR 原始输出转换为标准化的 ExamQuestion 结构
处理题目分离、作答区定位、选项解析
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.exceptions import BadRequestException


class ParsedQuestion:
    """解析后的题目对象"""

    def __init__(
        self,
        sequence: int = 0,
        question_type: str = "unknown",
        content: str = "",
        content_latex: str = "",
        options: Optional[Dict[str, str]] = None,
        score: float = 0.0,
        bbox: Optional[Dict[str, float]] = None,
        answer_area: Optional[Dict[str, float]] = None,
        page_number: int = 1,
        ocr_confidence: float = 0.0,
    ):
        self.sequence = sequence
        self.question_type = question_type
        self.content = content
        self.content_latex = content_latex
        self.options = options or {}
        self.score = score
        self.bbox = bbox or {}
        self.answer_area = answer_area or {}
        self.page_number = page_number
        self.ocr_confidence = ocr_confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence": self.sequence,
            "type": self.question_type,
            "content": self.content,
            "content_latex": self.content_latex,
            "options": self.options,
            "score": self.score,
            "bbox": self.bbox,
            "answer_area": self.answer_area,
            "page_number": self.page_number,
            "ocr_confidence": self.ocr_confidence,
        }


class LayoutParser:
    """试卷版面分析器"""

    # 题型关键词映射
    TYPE_PATTERNS = {
        "choice": ["选择题", "单选", "多选", "选出", "选项"],
        "fill_blank": ["填空题", "填写", "空格", "横线"],
        "short_answer": ["简答题", "简述", "说明", "阐述"],
        "calculation": ["计算题", "求解", "算出", "求值"],
        "proof": ["证明题", "求证", "证明"],
    }

    # 选项匹配正则
    OPTION_PATTERN = re.compile(r"[（(]\s*([A-Da-d])\s*[）)]\s*[\.．]?\s*(.+?)(?=[（(][A-Da-d][）)]|$)", re.DOTALL)
    OPTION_PATTERN_SIMPLE = re.compile(r"^([A-Da-d])[\.．、]\s*(.+)$", re.MULTILINE)

    @staticmethod
    def parse_ocr_result(
        ocr_data: Dict[str, Any],
        page_number: int = 1,
    ) -> List[ParsedQuestion]:
        """
        将 OCR 引擎输出的 JSON 解析为标准题目列表

        Args:
            ocr_data: OCR 引擎返回的 data 字段
            page_number: 页码

        Returns:
            ParsedQuestion 列表
        """
        questions_raw = ocr_data.get("questions", [])
        if not questions_raw:
            raise BadRequestException("OCR 结果中未识别到题目")

        parsed_questions = []
        for idx, q in enumerate(questions_raw):
            try:
                pq = LayoutParser._parse_single_question(q, page_number)
                parsed_questions.append(pq)
            except Exception as e:
                # 单题解析失败不阻断整体流程
                parsed_questions.append(
                    ParsedQuestion(
                        sequence=q.get("sequence", idx + 1),
                        question_type="unknown",
                        content=f"[解析失败] {str(e)}",
                        page_number=page_number,
                        ocr_confidence=0.0,
                    )
                )

        return parsed_questions

    @staticmethod
    def _parse_single_question(
        q: Dict[str, Any],
        page_number: int,
    ) -> ParsedQuestion:
        """解析单道题目"""
        sequence = q.get("sequence", 0)
        content = q.get("content", "").strip()
        content_latex = q.get("content_latex", "").strip()
        score = float(q.get("score", 0))
        bbox = q.get("bbox", {})
        answer_area = q.get("answer_area", {})
        ocr_confidence = q.get("ocr_confidence", 0.9)

        # 确定题型
        q_type = LayoutParser._detect_type(q.get("type", ""), content)

        # 解析选项（如果是选择题）
        options = {}
        if q_type == "choice":
            options = LayoutParser._extract_options(content)
            if not options:
                options = q.get("options", {})

        return ParsedQuestion(
            sequence=sequence,
            question_type=q_type,
            content=content,
            content_latex=content_latex,
            options=options,
            score=score,
            bbox=bbox,
            answer_area=answer_area,
            page_number=page_number,
            ocr_confidence=ocr_confidence,
        )

    @staticmethod
    def _detect_type(declared_type: str, content: str) -> str:
        """检测题目类型"""
        declared = declared_type.lower().strip()
        valid_types = ["choice", "fill_blank", "short_answer", "calculation", "proof"]
        if declared in valid_types:
            return declared

        # 根据内容推断
        content_lower = content.lower()
        for q_type, keywords in LayoutParser.TYPE_PATTERNS.items():
            for kw in keywords:
                if kw in content_lower:
                    return q_type

        # 如果有 A/B/C/D 选项，判定为选择题
        if LayoutParser._has_options(content):
            return "choice"

        # 如果有下划线或空格，判定为填空题
        if "___" in content or "……" in content or "【" in content:
            return "fill_blank"

        return "short_answer"

    @staticmethod
    def _has_options(text: str) -> bool:
        """检查是否包含选项"""
        return bool(
            LayoutParser.OPTION_PATTERN.search(text)
            or LayoutParser.OPTION_PATTERN_SIMPLE.search(text)
        )

    @staticmethod
    def _extract_options(text: str) -> Dict[str, str]:
        """从文本中提取选择题选项"""
        options = {}

        # 尝试第一种模式
        matches = LayoutParser.OPTION_PATTERN.findall(text)
        if matches:
            for key, value in matches:
                options[key.upper()] = value.strip()
            return options

        # 尝试第二种模式
        lines = text.split("\n")
        for line in lines:
            match = LayoutParser.OPTION_PATTERN_SIMPLE.match(line.strip())
            if match:
                key, value = match.groups()
                options[key.upper()] = value.strip()

        return options

    @staticmethod
    def merge_multi_page_questions(
        all_pages: List[List[ParsedQuestion]],
    ) -> List[ParsedQuestion]:
        """
        合并多页解析结果，重新排序题号
        """
        merged = []
        for page_questions in all_pages:
            merged.extend(page_questions)

        # 按 sequence 排序
        merged.sort(key=lambda q: q.sequence)

        # 重新编号（处理跨页题号可能重复的情况）
        seen_sequences = set()
        for idx, q in enumerate(merged, 1):
            if q.sequence in seen_sequences:
                q.sequence = idx
            seen_sequences.add(q.sequence)

        return merged

    @staticmethod
    def extract_answer_key_from_text(text: str) -> Dict[int, str]:
        """
        从标准答案文本中提取答案映射
        支持格式：
        - "1. A" / "1.A"
        - "1. 解：x=2"
        - "一、1. A"
        """
        answers = {}

        # 匹配 "题号. 答案"
        pattern = re.compile(r"(?:^|\n)\s*(\d+)\s*[\.．、]\s*([A-Da-d]|[^\n]+)")
        for match in pattern.finditer(text):
            seq = int(match.group(1))
            ans = match.group(2).strip()
            answers[seq] = ans

        return answers

    @staticmethod
    def validate_questions(questions: List[ParsedQuestion]) -> Tuple[List[ParsedQuestion], List[Dict]]:
        """
        验证题目质量，返回有效题目和警告列表
        """
        valid = []
        warnings = []

        for q in questions:
            issues = []

            if not q.content or len(q.content) < 5:
                issues.append("题目内容过短或为空")

            if q.question_type == "choice" and not q.options:
                issues.append("选择题未识别到选项")

            if q.ocr_confidence < 0.5:
                issues.append(f"OCR 置信度过低 ({q.ocr_confidence:.2f})")

            if issues:
                warnings.append({
                    "sequence": q.sequence,
                    "type": q.question_type,
                    "issues": issues,
                    "needs_review": True,
                })

            # 即使有问题也保留，但标记需人工审核
            valid.append(q)

        return valid, warnings


# 全局实例
layout_parser = LayoutParser()

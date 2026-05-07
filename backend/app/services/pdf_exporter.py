from __future__ import annotations

"""PDF 导出服务 —— 基于 reportlab."""

import os
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.error_book_item import ErrorBookItem
from app.models.report import Report


def _register_chinese_fonts() -> str:
    """注册中文字体并返回可用字体名."""
    candidates = [
        ("STHeiti", "/System/Library/Fonts/STHeiti Medium.ttc"),
        ("WenQuanYi", "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        ("SimHei", "/usr/share/fonts/truetype/simhei/SimHei.ttf"),
        ("ArialUnicode", "/Library/Fonts/Arial Unicode.ttf"),
    ]
    for name, path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception:
                continue
    # fallback: Helvetica（不支持中文，但保证不崩溃）
    return "Helvetica"


_FONT_NAME = _register_chinese_fonts()


def _make_styles() -> dict[str, ParagraphStyle]:
    """创建支持中文的 ParagraphStyle."""
    base = ParagraphStyle(
        "Base",
        fontName=_FONT_NAME,
        fontSize=11,
        leading=18,
        wordWrap="CJK",
    )
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base,
            fontSize=20,
            leading=28,
            alignment=1,  # center
            spaceAfter=20,
        ),
        "heading1": ParagraphStyle(
            "Heading1",
            parent=base,
            fontSize=16,
            leading=24,
            spaceAfter=12,
            textColor=colors.HexColor("#1a1a1a"),
        ),
        "heading2": ParagraphStyle(
            "Heading2",
            parent=base,
            fontSize=13,
            leading=20,
            spaceAfter=8,
            textColor=colors.HexColor("#333333"),
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base,
            fontSize=11,
            leading=18,
            spaceAfter=8,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base,
            fontSize=9,
            leading=14,
            textColor=colors.HexColor("#666666"),
        ),
        "center": ParagraphStyle(
            "Center",
            parent=base,
            alignment=1,
        ),
    }


class PDFExporter:
    """PDF 导出服务."""

    def __init__(self) -> None:
        self.styles = _make_styles()

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _build_doc(self, title: str) -> tuple[SimpleDocTemplate, BytesIO]:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2.5 * cm,
            bottomMargin=2 * cm,
            title=title,
        )
        return doc, buffer

    def _header_footer(self, canvas, doc):
        """页眉页脚回调."""
        canvas.saveState()
        canvas.setFont(_FONT_NAME, 9)
        canvas.setFillColor(colors.HexColor("#999999"))
        # 页眉
        canvas.drawString(2 * cm, A4[1] - 1.5 * cm, doc.title)
        # 页脚
        page_num = canvas.getPageNumber()
        canvas.drawRightString(A4[0] - 2 * cm, 1 * cm, f"第 {page_num} 页")
        canvas.drawString(2 * cm, 1 * cm, datetime.now(UTC).strftime("%Y-%m-%d"))
        canvas.restoreState()

    def _para(self, text: str, style_name: str = "body") -> Paragraph:
        """快捷创建 Paragraph."""
        return Paragraph(str(text).replace("\n", "<br/>"), self.styles[style_name])

    def _cover(self, title: str, lines: list[tuple[str, str]]) -> list[Any]:
        """生成封面内容."""
        story: list[Any] = [Spacer(1, 4 * cm)]
        story.append(Paragraph(title, self.styles["title"]))
        story.append(Spacer(1, 2 * cm))
        data = [[Paragraph(f"<b>{k}</b>", self.styles["body"]), Paragraph(v, self.styles["body"])] for k, v in lines]
        table = Table(data, colWidths=[4 * cm, 8 * cm])
        table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ])
        )
        story.append(table)
        story.append(PageBreak())
        return story

    # ------------------------------------------------------------------
    # 1. 错题本 PDF
    # ------------------------------------------------------------------

    async def export_error_book(
        self,
        student_id: int,
        error_items: list[ErrorBookItem],
    ) -> bytes:
        """导出错题本 PDF."""
        doc, buffer = self._build_doc("错题本")
        story: list[Any] = []

        # 封面
        story.extend(
            self._cover(
                "学生错题本",
                [
                    ("学生编号", str(student_id)),
                    ("导出日期", datetime.now(UTC).strftime("%Y-%m-%d %H:%M")),
                ],
            )
        )

        # 按知识点粗分组（使用 question_template_id 做 proxy）
        groups: dict[str, list[ErrorBookItem]] = {}
        for item in error_items:
            key = item.error_type or "未分类"
            groups.setdefault(key, []).append(item)

        # 目录
        story.append(Paragraph("目录", self.styles["heading1"]))
        for idx, (kp_name, _) in enumerate(groups.items(), 1):
            story.append(Paragraph(f"{idx}. {kp_name}", self.styles["body"]))
        story.append(PageBreak())

        # 每道错题
        for kp_name, items in groups.items():
            story.append(Paragraph(f"知识点：{kp_name}", self.styles["heading1"]))
            for item in items:
                story.append(Paragraph(f"错题 #{item.id}", self.styles["heading2"]))

                # 题目信息
                question_text = "（原题内容暂不可见）"
                correct_answer = "——"
                analysis = "——"
                if item.exam_question and item.exam_question.content:
                    question_text = item.exam_question.content
                elif item.question_template and item.question_template.content:
                    question_text = item.question_template.content

                if item.question_template and item.question_template.standard_answer:
                    correct_answer = item.question_template.standard_answer

                story.append(Paragraph("<b>【原题】</b>", self.styles["body"]))
                story.append(self._para(question_text))
                story.append(Paragraph("<b>【错误类型】</b> " + item.error_type, self.styles["body"]))
                story.append(Paragraph(f"<b>【错误次数】</b> {item.error_count}", self.styles["body"]))
                story.append(Paragraph("<b>【正解】</b>", self.styles["body"]))
                story.append(self._para(correct_answer))
                story.append(Paragraph("<b>【解析】</b>", self.styles["body"]))
                story.append(self._para(analysis))
                story.append(Paragraph(f"<b>【知识点标签】</b> {kp_name}", self.styles["body"]))
                story.append(Spacer(1, 0.5 * cm))
            story.append(PageBreak())

        doc.build(story, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        buffer.seek(0)
        return buffer.getvalue()

    # ------------------------------------------------------------------
    # 2. 诊断报告 PDF
    # ------------------------------------------------------------------

    async def export_report(
        self,
        report: Report,
    ) -> bytes:
        """导出诊断报告 PDF."""
        doc, buffer = self._build_doc(report.title or "诊断报告")
        story: list[Any] = []

        # 封面
        story.extend(
            self._cover(
                report.title or "学情诊断报告",
                [
                    ("学生 ID", str(report.student_id)),
                    ("报告类型", report.report_type.value if hasattr(report.report_type, "value") else str(report.report_type)),
                    ("生成日期", report.created_at.strftime("%Y-%m-%d %H:%M") if report.created_at else "——"),
                ],
            )
        )

        # 第 1 页：总体评价 + 分数统计
        story.append(Paragraph("一、总体评价", self.styles["heading1"]))
        story.append(self._para(report.overall_comment or "暂无总体评价"))
        score_info = [
            ["得分", str(report.total_score) if report.total_score is not None else "——"],
            ["满分", str(report.max_score) if report.max_score is not None else "——"],
            ["排名", str(report.rank) if report.rank is not None else "——"],
        ]
        t = Table(score_info, colWidths=[4 * cm, 8 * cm])
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, -1), _FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
        ]))
        story.append(t)
        story.append(PageBreak())

        # 第 2 页：薄弱知识点
        story.append(Paragraph("二、薄弱知识点", self.styles["heading1"]))
        weak_points = report.weak_points or []
        if weak_points:
            for wp in weak_points:
                name = wp.get("name") or wp.get("knowledge_point") or "未知"
                mastery = wp.get("mastery_level") or wp.get("mastery") or "——"
                story.append(Paragraph(f"• {name}（掌握度: {mastery}）", self.styles["body"]))
        else:
            story.append(Paragraph("暂无薄弱知识点记录", self.styles["body"]))
        story.append(PageBreak())

        # 第 3 页：错误类型分布
        story.append(Paragraph("三、错误类型分布", self.styles["heading1"]))
        error_dist = report.error_distribution or {}
        if isinstance(error_dist, dict):
            for k, v in error_dist.items():
                story.append(Paragraph(f"• {k}：{v} 次", self.styles["body"]))
        else:
            story.append(Paragraph("暂无错误分布数据", self.styles["body"]))
        story.append(PageBreak())

        # 第 4 页：学习建议
        story.append(Paragraph("四、学习建议", self.styles["heading1"]))
        recommendations = report.recommendations or []
        if recommendations:
            for rec in recommendations:
                term = rec.get("term") or rec.get("type") or "建议"
                content = rec.get("content") or ""
                story.append(Paragraph(f"<b>【{term}】</b>", self.styles["heading2"]))
                story.append(self._para(content))
        else:
            story.append(Paragraph("暂无学习建议", self.styles["body"]))
        story.append(PageBreak())

        # 第 5 页：下次考试目标
        story.append(Paragraph("五、下次考试目标", self.styles["heading1"]))
        story.append(Paragraph("基于当前学情分析，建议重点关注上述薄弱知识点，争取在下次考试中取得进步。", self.styles["body"]))

        doc.build(story, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        buffer.seek(0)
        return buffer.getvalue()

    # ------------------------------------------------------------------
    # 3. 考试成绩单 PDF（教师用）
    # ------------------------------------------------------------------

    async def export_exam_results(
        self,
        exam_id: int,
        results: list[dict],
    ) -> bytes:
        """导出考试成绩单 PDF（教师用）."""
        doc, buffer = self._build_doc(f"考试 {exam_id} 成绩单")
        story: list[Any] = []

        story.append(Paragraph(f"考试成绩单 — 考试 ID: {exam_id}", self.styles["title"]))
        story.append(Paragraph(f"导出时间：{datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}", self.styles["center"]))
        story.append(Spacer(1, 0.5 * cm))

        # 表头
        headers = ["排名", "学号", "姓名", "客观题得分", "主观题得分", "总分"]
        data = [headers]

        # 按总分排序
        sorted_results = sorted(
            results,
            key=lambda x: float(x.get("total_score", 0) or 0),
            reverse=True,
        )

        for rank, r in enumerate(sorted_results, 1):
            data.append([
                str(rank),
                str(r.get("student_number", "")),
                str(r.get("student_name", "")),
                str(r.get("objective_score", "")),
                str(r.get("subjective_score", "")),
                str(r.get("total_score", "")),
            ])

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a90d9")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), _FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, 0), 12),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f7f7f7")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 1), (-1, -1), _FONT_NAME),
            ("FONTSIZE", (0, 1), (-1, -1), 10),
        ]))
        story.append(table)

        doc.build(story, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        buffer.seek(0)
        return buffer.getvalue()

"""
核心流程端到端测试
验证：上传 -> OCR/版面分析 -> 判卷 -> 学科跟踪 的完整闭环
"""

import io
import json
import os
import sys
import unittest
from datetime import datetime, timezone

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFont

from app.services.grading_engine import grading_engine
from app.services.knowledge_tracker import knowledge_tracker
from app.services.layout_parser import ParsedQuestion, layout_parser
from app.services.pdf_service import pdf_service
from app.services.storage_service import StorageService


class TestCorePipeline(unittest.TestCase):
    """核心流程测试"""

    @classmethod
    def setUpClass(cls):
        """测试前准备"""
        print("\n" + "=" * 60)
        print("🧪 开始核心流程端到端测试")
        print("=" * 60)

    def _create_mock_exam_image(self) -> bytes:
        """
        创建模拟试卷图片（用于测试版面分析后的流程）
        """
        # 创建白色背景图片
        img = Image.new("RGB", (800, 1000), color="white")
        draw = ImageDraw.Draw(img)

        # 尝试使用系统字体
        try:
            font_title = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 24)
            font_text = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 18)
            font_math = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 20)
        except Exception:
            font_title = ImageFont.load_default()
            font_text = ImageFont.load_default()
            font_math = ImageFont.load_default()

        # 绘制试卷标题
        draw.text((250, 30), "2026年5月数学期中考试", fill="black", font=font_title)
        draw.line((50, 70, 750, 70), fill="black", width=2)

        # 题目 1：选择题
        draw.text((50, 100), "一、选择题（每题5分）", fill="black", font=font_text)
        draw.text((50, 140), "1. 二次函数 y = x² + 2x + 3 的顶点坐标是（  ）", fill="black", font=font_math)
        draw.text((80, 180), "A. (-1, 2)     B. (1, 2)     C. (-1, -2)     D. (1, -2)", fill="black", font=font_text)

        # 题目 2：填空题
        draw.text((50, 250), "二、填空题（每题5分）", fill="black", font=font_text)
        draw.text((50, 290), "2. 若函数 f(x) = x² - 4x + m 的最小值为 1，则 m = ______", fill="black", font=font_math)

        # 题目 3：计算题
        draw.text((50, 360), "三、计算题（每题10分）", fill="black", font=font_text)
        draw.text((50, 400), "3. 求函数 y = 2x² - 8x + 5 的顶点坐标和对称轴。", fill="black", font=font_math)
        draw.rectangle((50, 450, 750, 600), outline="gray", width=1)
        draw.text((60, 460), "解：", fill="black", font=font_text)

        # 题目 4：证明题
        draw.text((50, 650), "四、证明题（每题10分）", fill="black", font=font_text)
        draw.text((50, 690), "4. 证明：对于任意实数 x，x² + 2x + 3 > 0 恒成立。", fill="black", font=font_math)
        draw.rectangle((50, 740, 750, 900), outline="gray", width=1)
        draw.text((60, 750), "证明：", fill="black", font=font_text)

        # 保存为 bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

    def test_01_pdf_processing(self):
        """测试 PDF 处理功能"""
        print("\n📄 [测试 1/6] PDF 处理功能")

        # 创建一个简单的 PDF（使用 Pillow 的保存功能模拟）
        img = Image.new("RGB", (612, 792), color="white")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 20)
        except Exception:
            font = ImageFont.load_default()
        draw.text((100, 100), "数学试卷测试页", fill="black", font=font)
        draw.text((100, 150), "1. 1 + 1 = ?", fill="black", font=font)

        # 保存为 PDF
        pdf_buffer = io.BytesIO()
        img.save(pdf_buffer, format="PDF")
        pdf_bytes = pdf_buffer.getvalue()

        # 测试 PDF 信息提取
        info = pdf_service.get_pdf_info(pdf_bytes)
        self.assertEqual(info["page_count"], 1)
        print(f"   ✅ PDF 信息提取: {info}")

        # 测试 PDF 转图片
        images = pdf_service.pdf_to_images(pdf_bytes, dpi=150)
        self.assertEqual(len(images), 1)
        page_num, img_bytes, fmt = images[0]
        self.assertEqual(page_num, 1)
        self.assertEqual(fmt, "png")
        self.assertGreater(len(img_bytes), 0)
        print(f"   ✅ PDF 转图片成功: {len(img_bytes)} bytes, format={fmt}")

        # 验证图片可读取
        loaded_img = Image.open(io.BytesIO(img_bytes))
        self.assertGreater(loaded_img.width, 0)
        self.assertGreater(loaded_img.height, 0)
        print(f"   ✅ 图片尺寸: {loaded_img.width}x{loaded_img.height}")

    def test_02_layout_parser(self):
        """测试版面分析功能"""
        print("\n📐 [测试 2/6] 版面分析功能")

        # 模拟 OCR 输出（实际应由多模态模型返回）
        mock_ocr_data = {
            "page_number": 1,
            "questions": [
                {
                    "sequence": 1,
                    "type": "choice",
                    "content": "二次函数 y = x² + 2x + 3 的顶点坐标是（  ）",
                    "content_latex": "二次函数 $y = x^2 + 2x + 3$ 的顶点坐标是",
                    "options": {"A": "(-1, 2)", "B": "(1, 2)", "C": "(-1, -2)", "D": "(1, -2)"},
                    "score": 5,
                    "bbox": {"x": 0.05, "y": 0.12, "width": 0.9, "height": 0.1},
                    "answer_area": {"x": 0.05, "y": 0.18, "width": 0.9, "height": 0.05},
                },
                {
                    "sequence": 2,
                    "type": "fill_blank",
                    "content": "若函数 f(x) = x² - 4x + m 的最小值为 1，则 m = ______",
                    "content_latex": "若函数 $f(x) = x^2 - 4x + m$ 的最小值为 $1$，则 $m = $",
                    "options": {},
                    "score": 5,
                    "bbox": {"x": 0.05, "y": 0.28, "width": 0.9, "height": 0.08},
                    "answer_area": {"x": 0.7, "y": 0.28, "width": 0.2, "height": 0.05},
                },
                {
                    "sequence": 3,
                    "type": "calculation",
                    "content": "求函数 y = 2x² - 8x + 5 的顶点坐标和对称轴。",
                    "content_latex": "求函数 $y = 2x^2 - 8x + 5$ 的顶点坐标和对称轴。",
                    "options": {},
                    "score": 10,
                    "bbox": {"x": 0.05, "y": 0.38, "width": 0.9, "height": 0.08},
                    "answer_area": {"x": 0.05, "y": 0.46, "width": 0.9, "height": 0.15},
                },
            ],
        }

        # 解析
        questions = layout_parser.parse_ocr_result(mock_ocr_data, page_number=1)
        self.assertEqual(len(questions), 3)
        print(f"   ✅ 解析题目数量: {len(questions)}")

        # 验证每道题
        q1 = questions[0]
        self.assertEqual(q1.sequence, 1)
        self.assertEqual(q1.question_type, "choice")
        self.assertEqual(len(q1.options), 4)
        self.assertEqual(q1.score, 5)
        print(f"   ✅ Q1: 选择题, 4个选项, 满分{q1.score}")

        q2 = questions[1]
        self.assertEqual(q2.question_type, "fill_blank")
        self.assertEqual(q2.score, 5)
        print(f"   ✅ Q2: 填空题, 满分{q2.score}")

        q3 = questions[2]
        self.assertEqual(q3.question_type, "calculation")
        self.assertEqual(q3.score, 10)
        print(f"   ✅ Q3: 计算题, 满分{q3.score}")

        # 验证题目质量
        valid, warnings = layout_parser.validate_questions(questions)
        self.assertEqual(len(valid), 3)
        print(f"   ✅ 题目验证通过, 警告数: {len(warnings)}")

    def test_03_answer_key_extraction(self):
        """测试标准答案解析"""
        print("\n🔑 [测试 3/6] 标准答案解析")

        answer_text = """
一、选择题
1. A
2. C
3. B

二、填空题
4. 5
5. x = 2

三、计算题
6. 顶点坐标为 (2, -3)，对称轴为 x = 2
"""

        answers = layout_parser.extract_answer_key_from_text(answer_text)
        self.assertIn(1, answers)
        self.assertIn(2, answers)
        self.assertIn(3, answers)
        self.assertEqual(answers[1], "A")
        self.assertEqual(answers[2], "C")
        print(f"   ✅ 解析答案数量: {len(answers)}")
        print(f"   ✅ 答案映射: {answers}")

    def test_04_grading_objective(self):
        """测试客观题判卷"""
        print("\n✅ [测试 4/6] 客观题判卷引擎")

        # 测试选择题 - 正确
        result = grading_engine._grade_objective(
            question_type="choice",
            standard_answer="A",
            student_answer="A",
            max_score=5.0,
        )
        self.assertTrue(result.is_correct)
        self.assertEqual(result.score, 5.0)
        self.assertEqual(result.error_type, "correct")
        print(f"   ✅ 选择题正确: {result.score}/{result.max_score}")

        # 测试选择题 - 错误
        result = grading_engine._grade_objective(
            question_type="choice",
            standard_answer="A",
            student_answer="B",
            max_score=5.0,
        )
        self.assertFalse(result.is_correct)
        self.assertEqual(result.score, 0.0)
        print(f"   ✅ 选择题错误: {result.score}/{result.max_score}, 错因={result.error_type}")

        # 测试填空题 - 数值等价
        result = grading_engine._grade_objective(
            question_type="fill_blank",
            standard_answer="1/2",
            student_answer="0.5",
            max_score=5.0,
        )
        self.assertTrue(result.is_correct)
        self.assertEqual(result.score, 5.0)
        print(f"   ✅ 填空题数值等价(1/2=0.5): {result.score}/{result.max_score}")

        # 测试填空题 - 错误
        result = grading_engine._grade_objective(
            question_type="fill_blank",
            standard_answer="5",
            student_answer="3",
            max_score=5.0,
        )
        self.assertFalse(result.is_correct)
        self.assertEqual(result.score, 0.0)
        print(f"   ✅ 填空题错误: {result.score}/{result.max_score}, 错因={result.error_type}")

        # 测试未作答
        result = grading_engine._grade_objective(
            question_type="choice",
            standard_answer="A",
            student_answer="",
            max_score=5.0,
        )
        self.assertFalse(result.is_correct)
        self.assertEqual(result.error_type, "incomplete")
        print(f"   ✅ 未作答检测: 错因={result.error_type}")

    def test_05_knowledge_tracking(self):
        """测试学科跟踪（BKT + ELO）"""
        print("\n📊 [测试 5/6] 学科跟踪算法")

        student_id = 101
        kp_id = 1  # 假设知识点 ID

        # 初始状态
        state = knowledge_tracker.get_state(student_id, kp_id)
        self.assertAlmostEqual(state.mastery_probability, 0.5, places=2)
        print(f"   ✅ 初始掌握度: {state.mastery_probability:.4f}")

        # 第一次答错（计算错误）
        state = knowledge_tracker.update_from_grading(
            student_id=student_id,
            knowledge_point_id=kp_id,
            is_correct=False,
            error_type="calculation_error",
            question_difficulty=3.0,
        )
        self.assertLess(state.mastery_probability, 0.5)
        print(f"   ✅ 第一次答错后: {state.mastery_probability:.4f}")

        # 第二次答对（简单题）
        state = knowledge_tracker.update_from_grading(
            student_id=student_id,
            knowledge_point_id=kp_id,
            is_correct=True,
            question_difficulty=2.0,
        )
        self.assertGreater(state.mastery_probability, 0.35)
        print(f"   ✅ 第二次答对后: {state.mastery_probability:.4f}")

        # 连续答对 3 次
        for i in range(3):
            state = knowledge_tracker.update_from_grading(
                student_id=student_id,
                knowledge_point_id=kp_id,
                is_correct=True,
                question_difficulty=3.0,
            )
        self.assertGreater(state.mastery_probability, 0.7)
        print(f"   ✅ 连续答对3次后: {state.mastery_probability:.4f}, 状态={state.get_status()}")

        # 验证薄弱点检测
        weak_points = knowledge_tracker.get_weak_points(student_id=student_id, top_k=5)
        print(f"   ✅ 薄弱点检测: 共 {len(weak_points)} 个薄弱点")

        # 验证雷达图
        dimension_kps = {
            "函数与方程": [1, 2, 3],
            "几何": [4, 5, 6],
        }
        radar = knowledge_tracker.get_radar_data(student_id, dimension_kps)
        self.assertEqual(len(radar), 2)
        print(f"   ✅ 雷达图数据: {radar}")

        # 验证趋势
        history = [
            {"date": "2026-03-01", "is_correct": False},
            {"date": "2026-03-15", "is_correct": True},
            {"date": "2026-04-01", "is_correct": True},
        ]
        trend = knowledge_tracker.get_mastery_trend(student_id, kp_id, history)
        self.assertEqual(len(trend), 3)
        print(f"   ✅ 掌握度趋势: {[t['mastery'] for t in trend]}")

    def test_06_class_heatmap(self):
        """测试班级热力图"""
        print("\n🔥 [测试 6/6] 班级热力图")

        # 模拟 3 个学生，5 个知识点
        student_ids = [201, 202, 203]
        kp_ids = [1, 2, 3, 4, 5]

        # 为每个学生设置不同的掌握度
        for sid in student_ids:
            for i, kp_id in enumerate(kp_ids):
                # 学生 201 整体较弱，学生 203 整体较强
                base = 0.3 if sid == 201 else (0.7 if sid == 203 else 0.5)
                mastery = base + (i * 0.05)
                state = knowledge_tracker.get_state(sid, kp_id)
                state.mastery_probability = min(0.95, mastery)
                state.total_attempts = 10
                state.correct_count = int(state.mastery_probability * 10)
                state.last_graded_at = datetime.now(timezone.utc)

        heatmap = knowledge_tracker.calculate_class_heatmap(student_ids, kp_ids)
        self.assertEqual(len(heatmap), 5)
        print(f"   ✅ 热力图条目数: {len(heatmap)}")

        # 验证排序（按薄弱比例降序）
        for i in range(len(heatmap) - 1):
            self.assertGreaterEqual(
                heatmap[i]["weak_ratio"],
                heatmap[i + 1]["weak_ratio"],
            )

        for h in heatmap:
            print(f"   📊 KP {h['knowledge_point_id']}: 平均掌握度={h['class_mastery_avg']}, "
                  f"薄弱人数={h['student_count_below_0.5']}/{h['total_students']}, "
                  f"颜色={h['color']}")

    def test_07_full_pipeline_mock(self):
        """模拟完整流程：上传 -> 解析 -> 判卷 -> 跟踪"""
        print("\n🔄 [集成测试] 完整流程模拟")

        # 1. 创建模拟试卷数据
        mock_ocr_data = {
            "page_number": 1,
            "questions": [
                {
                    "sequence": 1,
                    "type": "choice",
                    "content": "二次函数 y = x² + 2x + 3 的顶点坐标是",
                    "options": {"A": "(-1, 2)", "B": "(1, 2)", "C": "(-1, -2)", "D": "(1, -2)"},
                    "score": 5,
                },
                {
                    "sequence": 2,
                    "type": "fill_blank",
                    "content": "若 f(x) = x² - 4x + m 最小值为 1，则 m = ",
                    "score": 5,
                },
                {
                    "sequence": 3,
                    "type": "calculation",
                    "content": "求 y = 2x² - 8x + 5 的顶点坐标",
                    "score": 10,
                },
            ],
        }

        # 2. 版面解析
        questions = layout_parser.parse_ocr_result(mock_ocr_data)
        self.assertEqual(len(questions), 3)
        print(f"   ✅ 步骤1-版面解析: {len(questions)} 道题")

        # 3. 标准答案
        answer_key = {1: "A", 2: "5", 3: "顶点坐标 (2, -3)，对称轴 x=2"}

        # 4. 学生作答
        student_answers = {"1": "A", "2": "3", "3": "顶点坐标是 (2, -3)"}

        # 5. 异步判卷
        import asyncio
        results_async = asyncio.run(self._async_grade(questions, answer_key, student_answers))

        # 准备知识更新
        knowledge_updates = []
        for r in results_async["details"]:
            kp_ids = [1, 2, 3]  # 假设映射到知识点 1,2,3
            for kp_id in kp_ids:
                knowledge_updates.append({
                    "knowledge_point_id": kp_id,
                    "is_correct": r["is_correct"],
                    "error_type": r["error_type"],
                    "question_difficulty": 3.0,
                })

        print(f"   ✅ 步骤2-判卷完成: 总分 {results_async['total_score']}/{results_async['max_score']}")
        for r in results_async["details"]:
            status = "✅" if r["is_correct"] else "❌"
            print(f"      {status} Q{r['sequence']}: {r['score']}分, 错因={r['error_type']}")

        # 6. 知识状态更新
        student_id = 999
        updated = knowledge_tracker.batch_update(student_id, knowledge_updates)
        print(f"   ✅ 步骤3-知识跟踪: 更新 {len(updated)} 个知识点状态")

        # 7. 获取薄弱点
        weak = knowledge_tracker.get_weak_points(student_id, top_k=3)
        print(f"   ✅ 步骤4-薄弱点分析: {len(weak)} 个薄弱点")

        print("\n🎉 完整流程测试通过！")

    async def _async_grade(self, questions, answer_key, student_answers):
        """异步判卷辅助方法"""
        results = []
        total_score = 0.0
        max_score = 0.0

        for q in questions:
            seq = q.sequence
            std_ans = answer_key.get(seq, "")
            stu_ans = student_answers.get(str(seq), "")

            result = await grading_engine.grade(
                question_type=q.question_type,
                question_content=q.content,
                standard_answer=std_ans,
                student_answer=stu_ans,
                max_score=q.score,
            )

            results.append({
                "sequence": seq,
                "is_correct": result.is_correct,
                "score": result.score,
                "error_type": result.error_type,
            })
            total_score += result.score
            max_score += q.score

        return {
            "total_score": total_score,
            "max_score": max_score,
            "details": results,
        }


if __name__ == "__main__":
    unittest.main(verbosity=2)

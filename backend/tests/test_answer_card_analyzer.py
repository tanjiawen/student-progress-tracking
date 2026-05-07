"""
答题卡分析服务测试（方案B正式版）
测试 AnswerCardAnalyzer 的完整流程
"""

import asyncio
import json
from pathlib import Path

import sys

# 确保能导入 app 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.answer_card_analyzer import AnswerCardAnalyzer

PROJECT_ROOT = Path(__file__).parent.parent.parent
OCR_JSON_PATH = PROJECT_ROOT / "test" / "answer_card_ocr_result.json"


async def main():
    print("=" * 70)
    print("📝 答题卡分析服务测试（方案B正式版）")
    print("=" * 70)

    # 加载 OCR 数据
    if not OCR_JSON_PATH.exists():
        print(f"❌ OCR 数据不存在: {OCR_JSON_PATH}")
        return

    ocr_data = json.loads(OCR_JSON_PATH.read_text(encoding="utf-8"))
    print(f"✅ 加载 OCR 数据: {ocr_data['student_info']['name']} ({ocr_data['student_info']['class']})")
    print(f"   考试: {ocr_data['exam_info']['title']}")
    print(f"   得分: {ocr_data['exam_info']['total_score']} / {ocr_data['exam_info']['max_score']}")

    # 初始化分析器
    analyzer = AnswerCardAnalyzer()

    try:
        # 生成完整报告
        print("\n🔄 正在生成完整分析报告...")
        report = await analyzer.generate_full_report(ocr_data)

        print("\n" + "=" * 70)
        print("📋 学情分析报告")
        print("=" * 70)

        if report.learning_analysis:
            la = report.learning_analysis
            print(f"\n【总体评价】\n{la.overall_evaluation}")

            print(f"\n【已掌握知识点】({len(la.mastered_knowledge)}个)")
            for k in la.mastered_knowledge:
                print(f"  ✅ {k}")

            print(f"\n【薄弱知识点】({len(la.weak_knowledge)}个)")
            for k in la.weak_knowledge:
                print(f"  ❌ {k}")

            print(f"\n【错误模式】({len(la.error_patterns)}种)")
            for ep in la.error_patterns:
                print(f"  🔍 {ep.get('type', '未知')}: {ep.get('description', '')}")
                if ep.get('examples'):
                    print(f"     示例: {', '.join(ep['examples'])}")

            print(f"\n【短期建议】(1周内)")
            for s in la.short_term_suggestions:
                print(f"  📌 {s}")

            print(f"\n【中期建议】(1个月内)")
            for s in la.mid_term_suggestions:
                print(f"  📌 {s}")

            print(f"\n【下次考试目标】{la.next_exam_target} 分")
            print(f"   模型: {la.model}")
            print(f"   Token: {la.usage.get('total_tokens', '?')}")

        print("\n" + "=" * 70)
        print("📊 知识点掌握度评估")
        print("=" * 70)

        priority_items = [k for k in report.knowledge_mastery if k.priority_review]
        normal_items = [k for k in report.knowledge_mastery if not k.priority_review]

        print(f"\n【需优先复习】({len(priority_items)}个)")
        for k in priority_items:
            print(f"  🔴 {k.knowledge_point:20} | 掌握度: {k.mastery_level:.2f} | 建议难度: {k.suggested_difficulty}")

        print(f"\n【已掌握/正常】({len(normal_items)}个)")
        for k in normal_items:
            print(f"  🟢 {k.knowledge_point:20} | 掌握度: {k.mastery_level:.2f} | 建议难度: {k.suggested_difficulty}")

        # 保存报告
        report_path = PROJECT_ROOT / "test" / "answer_card_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"\n💾 完整报告已保存: {report_path}")

    finally:
        await analyzer.close()

    print("\n" + "=" * 70)
    print("🎉 方案B正式版测试完成！")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

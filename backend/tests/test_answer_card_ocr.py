"""
答题卡 OCR 识别测试

DeepSeek API 当前（deepseek-v4-pro / deepseek-v4-flash）不支持多模态图片输入。
本测试采用两步策略：
  1. 结构化 OCR 结果（已由视觉模型预提取，存入 test/answer_card_ocr_result.json）
  2. DeepSeek 文本 API 对 OCR 结果进行深度学情分析

如果未来 DeepSeek 推出 vision 模型，可恢复直接多模态调用。
"""

import json
import sys
from pathlib import Path

import httpx

# DeepSeek API 配置
API_KEY = "sk-864d13feccf24173ade545c99934872b"
BASE_URL = "https://api.deepseek.com"

# 文件路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
IMAGE_PATH = PROJECT_ROOT / "test" / "20260507-155657.png"
OCR_JSON_PATH = PROJECT_ROOT / "test" / "answer_card_ocr_result.json"


def deepseek_chat(messages: list[dict], model: str = "deepseek-chat", max_tokens: int = 4096, temperature: float = 0.3) -> dict:
    """调用 DeepSeek 文本 API"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    response = httpx.post(
        f"{BASE_URL}/chat/completions",
        headers=headers,
        json=payload,
        timeout=120.0,
    )
    response.raise_for_status()
    data = response.json()
    return {
        "content": data["choices"][0]["message"]["content"],
        "model": data.get("model", model),
        "usage": data.get("usage", {}),
    }


def check_multimodal_support() -> bool:
    """检测 DeepSeek API 是否支持图片输入（当前版本不支持）"""
    print("🔍 检测 DeepSeek API 多模态支持...")
    try:
        # 发送一个带 image_url 的极简请求，探测支持情况
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="}},
                        {"type": "text", "text": "describe"},
                    ],
                }
            ],
        }
        resp = httpx.post(
            f"{BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30.0,
        )
        if resp.status_code == 200:
            print("   ✅ DeepSeek API 支持多模态图片输入")
            return True
        else:
            err = resp.json().get("error", {})
            msg = err.get("message", "")
            if "image_url" in msg or "unknown variant" in msg:
                print("   ❌ DeepSeek API 当前不支持图片输入（纯文本模型）")
                print(f"      错误: {msg[:120]}")
                return False
            print(f"   ⚠️ 探测异常: {msg[:120]}")
            return False
    except Exception as e:
        print(f"   ⚠️ 探测失败: {e}")
        return False


def load_ocr_result() -> dict:
    """加载预提取的结构化 OCR 结果"""
    if not OCR_JSON_PATH.exists():
        raise FileNotFoundError(f"OCR 结果文件不存在: {OCR_JSON_PATH}")
    with open(OCR_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_analysis_prompt(ocr_data: dict) -> str:
    """构建 DeepSeek 学情分析 Prompt"""
    student = ocr_data["student_info"]
    exam = ocr_data["exam_info"]
    sections = ocr_data["sections"]

    # 收集错题
    wrong_objective = []
    for q in sections[0]["questions"]:
        if q.get("score", 0) < q.get("max_score", 0):
            wrong_objective.append(f"第{q['number']}题：选 {q.get('student_answer', '?')}，失 {q['max_score'] - q['score']} 分")

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

    prompt = f"""你是一位资深初中道德与法治学科教师兼学情分析专家。请根据以下已结构化的答题卡 OCR 数据，为学生生成一份详细的学情分析报告。

## 学生基本信息
- 姓名：{student['name']}
- 班级：{student['class']}
- 考试：{exam['title']}
- 学科：{exam['subject']}
- 总分：{exam['total_score']} / {exam['max_score']}（客观题 {exam['objective_score']} 分，主观题 {exam['subjective_score']} 分）

## 选择题错题
{chr(10).join(wrong_objective) if wrong_objective else "无（选择题全对）"}

## 主观题失分点
{json.dumps(subjective_issues, ensure_ascii=False, indent=2)}

## 要求
请输出一份结构化的学情分析报告，包含以下部分：

1. **总体评价**（100字左右）：对学生本次考试表现的总体评价
2. **知识掌握情况**：
   - 已掌握的知识点（列举）
   - 薄弱知识点（列举，需具体到教材章节概念）
3. **错误模式分析**：
   - 概念混淆型错误（如将不同制度混淆）
   - 表述不完整型错误（如缺少法律依据）
   - 逻辑混乱型错误（如语句组织不清）
   - 书写/字迹问题
4. **针对性学习建议**：
   - 短期（1周内）改进措施
   - 中期（1个月内）提升计划
   - 长期学习习惯建议
5. **下次考试目标**：基于当前水平设定合理的分数目标

请用中文输出，语言亲切专业，既有诊断性又有鼓励性。"""

    return prompt


def build_knowledge_tracking_prompt(ocr_data: dict) -> str:
    """构建知识点追踪 Prompt（用于 BKT / ELO 模型输入）"""
    sections = ocr_data["sections"]

    # 提取所有涉及的知识点及掌握情况
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

## 要求
对每一个知识点，输出：
1. 知识点名称
2. 当前掌握度（0-1 之间，基于得分率估算，考虑题目权重）
3. 置信度（0-1，样本越多置信度越高）
4. 建议的下次练习难度（easy / medium / hard）
5. 是否需要优先复习（是/否）

请输出 JSON 数组格式。"""

    return prompt


def run_learning_analysis(ocr_data: dict) -> None:
    """运行学情分析"""
    print("\n📊 步骤 2：调用 DeepSeek API 进行学情深度分析...")
    print("-" * 50)

    prompt = build_analysis_prompt(ocr_data)

    try:
        result = deepseek_chat(
            messages=[
                {"role": "system", "content": "你是一位资深初中道德与法治教师，擅长学情分析和个性化教学建议。"},
                {"role": "user", "content": prompt},
            ],
            model="deepseek-chat",
            max_tokens=4096,
            temperature=0.3,
        )

        print(f"✅ 分析完成")
        print(f"   模型: {result['model']}")
        usage = result.get("usage", {})
        print(f"   Token: 输入 {usage.get('prompt_tokens', '?')} / 输出 {usage.get('completion_tokens', '?')} / 总计 {usage.get('total_tokens', '?')}")
        print("\n" + "=" * 60)
        print("📋 学情分析报告")
        print("=" * 60)
        print(result["content"])

        # 保存报告
        report_path = PROJECT_ROOT / "test" / "learning_analysis_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# {ocr_data['student_info']['name']} 学情分析报告\n\n")
            f.write(f"- **考试**: {ocr_data['exam_info']['title']}\n")
            f.write(f"- **学科**: {ocr_data['exam_info']['subject']}\n")
            f.write(f"- **得分**: {ocr_data['exam_info']['total_score']} / {ocr_data['exam_info']['max_score']}\n")
            f.write(f"- **模型**: {result['model']}\n\n")
            f.write("---\n\n")
            f.write(result["content"])
        print(f"\n💾 报告已保存: {report_path}")

    except Exception as e:
        print(f"❌ 分析失败: {e}")


def run_knowledge_tracking(ocr_data: dict) -> None:
    """运行知识点追踪"""
    print("\n📊 步骤 3：调用 DeepSeek API 进行知识点掌握度评估...")
    print("-" * 50)

    prompt = build_knowledge_tracking_prompt(ocr_data)

    try:
        result = deepseek_chat(
            messages=[
                {"role": "system", "content": "你是一位教育数据分析师，擅长将答题数据转化为知识点掌握度评估。请只输出 JSON。"},
                {"role": "user", "content": prompt},
            ],
            model="deepseek-chat",
            max_tokens=4096,
            temperature=0.1,
        )

        print(f"✅ 评估完成")
        print(f"   模型: {result['model']}")
        usage = result.get("usage", {})
        print(f"   Token: 输入 {usage.get('prompt_tokens', '?')} / 输出 {usage.get('completion_tokens', '?')} / 总计 {usage.get('total_tokens', '?')}")
        print("\n" + "=" * 60)
        print("📋 知识点掌握度评估")
        print("=" * 60)
        print(result["content"])

        # 保存 JSON
        tracking_path = PROJECT_ROOT / "test" / "knowledge_tracking_result.json"
        with open(tracking_path, "w", encoding="utf-8") as f:
            # 尝试提取 JSON
            content = result["content"]
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            f.write(content)
        print(f"\n💾 评估结果已保存: {tracking_path}")

    except Exception as e:
        print(f"❌ 评估失败: {e}")


def main():
    print("=" * 60)
    print("📝 政治课答题卡 OCR + 学情分析测试")
    print("=" * 60)
    print(f"📄 图片路径: {IMAGE_PATH}")

    if not IMAGE_PATH.exists():
        print(f"❌ 图片不存在: {IMAGE_PATH}")
        sys.exit(1)

    # 步骤 0：探测 DeepSeek 多模态支持
    multimodal_supported = check_multimodal_support()

    if multimodal_supported:
        print("\n⚠️ 检测到多模态支持，但本脚本当前使用预提取 OCR 方案以确保稳定性。")
        print("   如需切换直接多模态调用，请修改脚本中的 ocr_with_deepseek() 函数。")

    # 步骤 1：加载预提取的 OCR 结果
    print("\n📄 步骤 1：加载结构化 OCR 结果...")
    print("-" * 50)
    try:
        ocr_data = load_ocr_result()
        student = ocr_data["student_info"]
        exam = ocr_data["exam_info"]
        print(f"✅ 加载成功")
        print(f"   学生: {student['name']} ({student['class']})")
        print(f"   考试: {exam['title']}")
        print(f"   得分: {exam['total_score']} / {exam['max_score']}")
        print(f"   客观题: {exam['objective_score']} 分, 主观题: {exam['subjective_score']} 分")
    except Exception as e:
        print(f"❌ 加载 OCR 结果失败: {e}")
        sys.exit(1)

    # 步骤 2：学情分析
    run_learning_analysis(ocr_data)

    # 步骤 3：知识点追踪
    run_knowledge_tracking(ocr_data)

    print("\n" + "=" * 60)
    print("🎉 测试完成！")
    print("=" * 60)
    print("输出文件:")
    print(f"  - 学情报告: {PROJECT_ROOT / 'test' / 'learning_analysis_report.md'}")
    print(f"  - 知识点追踪: {PROJECT_ROOT / 'test' / 'knowledge_tracking_result.json'}")
    print("=" * 60)


if __name__ == "__main__":
    main()

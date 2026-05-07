"""
考试/试卷 API 路由
核心功能：上传、OCR、题目解析、判卷
"""

from typing import Any, List, Optional

from fastapi import APIRouter, File, Form, UploadFile, status

from app.core.exceptions import BadRequestException
from app.services.grading_engine import GradingResult, grading_engine
from app.services.knowledge_tracker import knowledge_tracker
from app.services.layout_parser import ParsedQuestion, layout_parser
from app.services.pdf_service import pdf_service
from app.services.storage_service import storage_service

router = APIRouter()


# 内存中的临时存储（实际应使用数据库）
_exams: dict[int, dict] = {}
_exam_questions: dict[int, List[ParsedQuestion]] = {}
_next_exam_id = 1


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_exam(
    file: UploadFile = File(...),
    title: str = Form(""),
    subject: str = Form("数学"),
) -> Any:
    """
    上传考试试卷（PDF 或图片）

    - file: PDF 或图片文件
    - title: 考试名称
    - subject: 学科
    """
    global _next_exam_id

    if not file.filename:
        raise BadRequestException("未提供文件")

    # 读取文件内容
    contents = await file.read()
    if len(contents) == 0:
        raise BadRequestException("文件为空")

    # 判断文件类型
    content_type = file.content_type or ""
    is_pdf = content_type == "application/pdf" or file.filename.lower().endswith(".pdf")
    is_image = content_type.startswith("image/") or any(
        file.filename.lower().endswith(ext)
        for ext in [".jpg", ".jpeg", ".png", ".webp"]
    )

    if not is_pdf and not is_image:
        raise BadRequestException("仅支持 PDF 或图片格式（jpg/png/webp）")

    # 创建考试记录
    exam_id = _next_exam_id
    _next_exam_id += 1

    exam = {
        "id": exam_id,
        "title": title or f"考试 {exam_id}",
        "subject": subject,
        "filename": file.filename,
        "status": "uploaded",
        "pages": [],
        "questions": [],
    }

    # 处理 PDF：转图片
    if is_pdf:
        pdf_info = pdf_service.get_pdf_info(contents)
        images = pdf_service.pdf_to_images(contents, dpi=300, enhance=True)

        for page_num, img_bytes, fmt in images:
            object_name = storage_service.upload_image(
                file_data=img_bytes,
                filename=f"page_{page_num}.{fmt}",
                exam_id=exam_id,
                page_number=page_num,
            )
            exam["pages"].append({
                "page_number": page_num,
                "object_name": object_name,
                "format": fmt,
            })

        exam["page_count"] = len(images)

    else:
        # 单张图片
        object_name = storage_service.upload_image(
            file_data=contents,
            filename=file.filename,
            exam_id=exam_id,
            page_number=1,
        )
        exam["pages"].append({
            "page_number": 1,
            "object_name": object_name,
            "format": file.filename.split(".")[-1].lower(),
        })
        exam["page_count"] = 1

    _exams[exam_id] = exam

    return {
        "success": True,
        "exam_id": exam_id,
        "title": exam["title"],
        "page_count": exam["page_count"],
        "status": "uploaded",
        "message": f"上传成功，共 {exam['page_count']} 页，请调用 /exams/{exam_id}/ocr 进行识别",
    }


@router.post("/{exam_id}/ocr")
async def ocr_exam(
    exam_id: int,
    provider: Optional[str] = None,
) -> Any:
    """
    对试卷进行 OCR 识别和版面分析

    - provider: 可选 qwen-vl / gpt-4o / mathpix，不指定则自动选择
    """
    from app.ai.ocr_engine import ocr_engine

    exam = _exams.get(exam_id)
    if not exam:
        raise BadRequestException("考试不存在")

    if exam["status"] not in ("uploaded", "ocr_failed"):
        raise BadRequestException(f"当前状态 {exam['status']} 不支持 OCR")

    exam["status"] = "processing"
    all_questions: List[ParsedQuestion] = []
    ocr_warnings = []

    for page in exam["pages"]:
        page_num = page["page_number"]
        object_name = page["object_name"]

        # 从 MinIO 读取图片
        img_bytes = storage_service.get_file_bytes(object_name)

        # OCR 识别
        try:
            ocr_result = await ocr_engine.analyze_exam_page(
                image_bytes=img_bytes,
                subject_hint=exam["subject"],
                preferred_provider=provider,
            )

            if not ocr_result["success"]:
                ocr_warnings.append(f"第 {page_num} 页识别失败")
                continue

            # 版面分析
            parsed = layout_parser.parse_ocr_result(
                ocr_data=ocr_result["data"],
                page_number=page_num,
            )

            # 验证题目质量
            valid, warnings = layout_parser.validate_questions(parsed)
            ocr_warnings.extend([f"第 {page_num} 页: {w['issues']}" for w in warnings])

            all_questions.extend(valid)
            page["ocr_provider"] = ocr_result["provider"]
            page["fallback_used"] = ocr_result.get("fallback_used", False)

        except Exception as e:
            ocr_warnings.append(f"第 {page_num} 页处理异常: {str(e)}")
            continue

    # 合并多页题目，重新排序
    if len(exam["pages"]) > 1:
        all_questions = layout_parser.merge_multi_page_questions(
            [[q for q in all_questions if q.page_number == p["page_number"]] for p in exam["pages"]]
        )

    # 保存题目
    _exam_questions[exam_id] = all_questions
    exam["questions"] = [q.to_dict() for q in all_questions]
    exam["status"] = "ocr_completed" if all_questions else "ocr_failed"
    exam["ocr_warnings"] = ocr_warnings

    return {
        "success": len(all_questions) > 0,
        "exam_id": exam_id,
        "question_count": len(all_questions),
        "status": exam["status"],
        "questions": exam["questions"],
        "warnings": ocr_warnings,
    }


@router.post("/{exam_id}/answer-key")
async def upload_answer_key(
    exam_id: int,
    file: UploadFile = File(...),
) -> Any:
    """上传标准答案（PDF 或文本文件）"""
    exam = _exams.get(exam_id)
    if not exam:
        raise BadRequestException("考试不存在")

    contents = await file.read()

    # 如果是 PDF，提取文本
    if file.filename and file.filename.lower().endswith(".pdf"):
        text = pdf_service.extract_text_from_pdf(contents)
    else:
        text = contents.decode("utf-8", errors="ignore")

    # 解析答案映射
    answers = layout_parser.extract_answer_key_from_text(text)

    # 保存到考试记录
    exam["answer_key"] = answers
    exam["answer_key_raw"] = text

    return {
        "success": True,
        "exam_id": exam_id,
        "answers_parsed": answers,
        "answer_count": len(answers),
    }


@router.post("/{exam_id}/grade")
async def grade_exam(
    exam_id: int,
    student_id: int = Form(1),
    answers: Optional[str] = Form(None),
) -> Any:
    """
    对考试进行判卷

    - answers: JSON 字符串，格式 {"1": "A", "2": "x=2"}
      如果不提供，则使用已上传的答题卡图片（待实现）
    """
    import json

    exam = _exams.get(exam_id)
    if not exam:
        raise BadRequestException("考试不存在")

    questions = _exam_questions.get(exam_id, [])
    if not questions:
        raise BadRequestException("请先完成 OCR 识别")

    answer_key = exam.get("answer_key", {})
    if not answer_key:
        raise BadRequestException("请先上传标准答案")

    # 解析学生答案
    student_answers = {}
    if answers:
        try:
            student_answers = json.loads(answers)
        except Exception:
            raise BadRequestException("answers 参数格式错误，应为 JSON 字符串")

    # 逐题判卷
    results = []
    knowledge_updates = []
    total_score = 0.0
    max_total = 0.0

    for q in questions:
        seq = q.sequence
        std_ans = answer_key.get(seq, "")
        stu_ans = student_answers.get(str(seq), "")

        # 判卷
        grading_result = await grading_engine.grade(
            question_type=q.question_type,
            question_content=q.content,
            standard_answer=std_ans,
            student_answer=stu_ans,
            max_score=q.score,
        )

        results.append({
            "sequence": seq,
            "question_type": q.question_type,
            "content": q.content,
            "standard_answer": std_ans,
            "student_answer": stu_ans,
            "grading": grading_result.to_dict(),
        })

        total_score += grading_result.score
        max_total += q.score

        # 准备知识状态更新
        for kp_id in grading_result.knowledge_point_ids:
            if isinstance(kp_id, int):
                knowledge_updates.append({
                    "knowledge_point_id": kp_id,
                    "is_correct": grading_result.is_correct,
                    "error_type": grading_result.error_type,
                    "question_difficulty": 3.0,  # 默认难度
                })

    # 批量更新知识状态
    updated_states = []
    if knowledge_updates:
        updated_states = knowledge_tracker.batch_update(
            student_id=student_id,
            results=knowledge_updates,
        )

    exam["status"] = "graded"
    exam["last_grading"] = {
        "student_id": student_id,
        "total_score": total_score,
        "max_score": max_total,
        "score_rate": round(total_score / max_total, 4) if max_total > 0 else 0,
        "results": results,
    }

    return {
        "success": True,
        "exam_id": exam_id,
        "student_id": student_id,
        "total_score": round(total_score, 2),
        "max_score": max_total,
        "score_rate": round(total_score / max_total, 4) if max_total > 0 else 0,
        "question_results": results,
        "knowledge_updates": [s.to_dict() for s in updated_states],
    }


@router.get("/{exam_id}")
async def get_exam(exam_id: int) -> Any:
    """获取考试详情"""
    exam = _exams.get(exam_id)
    if not exam:
        raise BadRequestException("考试不存在")
    return exam


@router.get("/{exam_id}/questions")
async def get_exam_questions(exam_id: int) -> Any:
    """获取考试题目列表"""
    exam = _exams.get(exam_id)
    if not exam:
        raise BadRequestException("考试不存在")
    return {
        "exam_id": exam_id,
        "questions": exam.get("questions", []),
    }

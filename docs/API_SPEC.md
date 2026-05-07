# API 接口规范（API Specification）

> Base URL: `/api/v1`  
> 认证方式: `Bearer <JWT>`  
> 数据格式: JSON  
> 分页参数: `page` (默认1), `page_size` (默认20, 最大100)

---

## 1. 认证模块 (Auth)

### POST `/auth/login`
用户登录
```json
// Request
{
  "username": "teacher01",
  "password": "string"
}

// Response 200
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": 1,
    "username": "teacher01",
    "real_name": "张老师",
    "role": "teacher",
    "avatar_url": "https://..."
  }
}
```

### POST `/auth/refresh`
刷新 Token
```json
// Request
{ "refresh_token": "..." }

// Response 200
{ "access_token": "...", "expires_in": 3600 }
```

### GET `/auth/me`
获取当前用户信息
```json
// Response 200
{
  "id": 1,
  "username": "teacher01",
  "real_name": "张老师",
  "role": "teacher",
  "email": "teacher@school.com",
  "phone": "13800138000",
  "permissions": ["exam:create", "report:view", "student:manage"]
}
```

---

## 2. 用户管理 (Users)

### GET `/users`
用户列表（管理员/教师）
```
Query: role=student&class_id=5&keyword=张&page=1&page_size=20
```
```json
// Response 200
{
  "total": 150,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "id": 101,
      "username": "stu2025001",
      "real_name": "李明",
      "role": "student",
      "grade": "高一",
      "class_name": "1班",
      "is_active": true,
      "created_at": "2025-09-01T08:00:00Z"
    }
  ]
}
```

### POST `/users`
创建用户
```json
// Request
{
  "username": "stu2025002",
  "password": "initial123",
  "real_name": "王芳",
  "role": "student",
  "email": "stu2@school.com",
  "phone": "13900139000",
  "class_ids": [5, 6]
}

// Response 201
{ "id": 102, "username": "stu2025002", ... }
```

### GET `/users/{id}`
用户详情
```json
// Response 200
{
  "id": 101,
  "username": "stu2025001",
  "real_name": "李明",
  "role": "student",
  "classes": [
    { "id": 5, "name": "高一1班", "subject": "数学" }
  ],
  "stats": {
    "total_exams": 12,
    "avg_score": 85.5,
    "weak_knowledge_points": 8,
    "last_exam_date": "2026-04-28"
  }
}
```

### PUT `/users/{id}`
更新用户信息

### DELETE `/users/{id}`
删除/禁用用户

---

## 3. 班级管理 (Classes)

### GET `/classes`
班级列表
```
Query: subject_id=1&grade=高一&teacher_id=2
```

### POST `/classes`
创建班级
```json
// Request
{
  "name": "高一1班",
  "grade": "高一",
  "subject_id": 1,
  "teacher_id": 2
}
```

### GET `/classes/{id}`
班级详情（含学生列表）
```json
// Response 200
{
  "id": 5,
  "name": "高一1班",
  "grade": "高一",
  "subject": { "id": 1, "name": "数学" },
  "teacher": { "id": 2, "real_name": "张老师" },
  "students": [
    { "id": 101, "real_name": "李明", "mastery_avg": 0.72 }
  ],
  "stats": {
    "student_count": 45,
    "exam_count": 8,
    "class_avg_mastery": 0.68
  }
}
```

### POST `/classes/{id}/students`
添加学生到班级
```json
// Request
{ "student_ids": [101, 102, 103] }
```

### DELETE `/classes/{id}/students/{student_id}`
移除学生

### GET `/classes/{id}/heatmap`
班级薄弱知识点热力图
```json
// Response 200
{
  "knowledge_points": [
    {
      "id": 15,
      "name": "二次函数顶点坐标",
      "class_mastery_avg": 0.45,
      "student_count_below_0.5": 28,
      "color": "#ff4d4f"
    }
  ]
}
```

---

## 4. 学科与知识图谱 (Subjects & Knowledge)

### GET `/subjects`
学科列表
```json
// Response 200
[
  { "id": 1, "name": "数学", "code": "math", "knowledge_point_count": 156 },
  { "id": 2, "name": "物理", "code": "physics", "knowledge_point_count": 98 }
]
```

### GET `/subjects/{id}/knowledge-points`
学科知识点树
```
Query: parent_id=&depth=3
```
```json
// Response 200
[
  {
    "id": 10,
    "name": "函数",
    "code": "MATH-FUNC",
    "level": 1,
    "children": [
      {
        "id": 15,
        "name": "二次函数",
        "code": "MATH-FUNC-QUAD",
        "level": 2,
        "children": [
          { "id": 152, "name": "顶点坐标计算", "code": "MATH-FUNC-QUAD-01", "level": 3 }
        ]
      }
    ]
  }
]
```

### POST `/knowledge-points`
创建知识点
```json
// Request
{
  "subject_id": 1,
  "parent_id": 15,
  "name": "顶点坐标计算",
  "code": "MATH-FUNC-QUAD-01",
  "level": 3,
  "description": "通过配方法或公式法求二次函数顶点坐标",
  "tags": ["代数", "计算"]
}
```

### GET `/knowledge-points/{id}/relations`
知识点关系
```json
// Response 200
{
  "prerequisites": [
    { "id": 120, "name": "一元二次方程求解", "relation_type": "prerequisite" }
  ],
  "extensions": [
    { "id": 153, "name": "二次函数最值应用", "relation_type": "extension" }
  ]
}
```

### POST `/knowledge-points/{id}/relations`
添加知识点关系
```json
// Request
{
  "to_kp_id": 153,
  "relation_type": "extension",
  "weight": 0.8
}
```

---

## 5. 考试与试卷 (Exams)

### GET `/exams`
考试列表
```
Query: class_id=5&status=graded&subject_id=1&from_date=2026-01-01&to_date=2026-05-01
```
```json
// Response 200
{
  "total": 8,
  "items": [
    {
      "id": 10,
      "title": "2026年4月期中考试",
      "subject": "数学",
      "exam_date": "2026-04-15",
      "status": "graded",
      "total_score": 150,
      "question_count": 22,
      "class_avg": 98.5,
      "created_at": "2026-04-10T10:00:00Z"
    }
  ]
}
```

### POST `/exams`
创建考试
```json
// Request
{
  "title": "2026年5月月考",
  "subject_id": 1,
  "class_id": 5,
  "exam_date": "2026-05-20",
  "total_score": 150,
  "description": "..."
}

// Response 201
{ "id": 11, "status": "draft", ... }
```

### POST `/exams/{id}/upload`
上传试卷图片/PDF
```
Content-Type: multipart/form-data

file: <binary>
page_number: 1
```
```json
// Response 200
{
  "file_url": "https://minio/.../exam_11_page1.jpg",
  "ocr_task_id": 55,
  "status": "processing"
}
```

### GET `/exams/{id}`
考试详情
```json
// Response 200
{
  "id": 10,
  "title": "2026年4月期中考试",
  "status": "graded",
  "questions": [
    {
      "id": 100,
      "sequence": 1,
      "type": "choice",
      "content": "二次函数 $y=x^2+2x+3$ 的顶点坐标是",
      "score": 5,
      "knowledge_points": ["MATH-FUNC-QUAD-01"],
      "class_correct_rate": 0.65
    }
  ],
  "class_stats": {
    "avg_score": 98.5,
    "max_score": 145,
    "min_score": 62,
    "std_dev": 18.3
  }
}
```

### POST `/exams/{id}/start-grading`
启动批量自动判卷
```json
// Request
{ "model": "deepseek-r1", "async": true }

// Response 202
{ "task_id": "celery-task-uuid", "status": "processing", "estimated_seconds": 120 }
```

### GET `/exams/{id}/grading-progress`
判卷进度
```json
// Response 200
{
  "total_questions": 22,
  "total_students": 45,
  "total_submissions": 990,
  "graded_count": 756,
  "progress": 0.76,
  "status": "processing",
  "started_at": "2026-05-07T14:00:00Z"
}
```

---

## 6. 题目管理 (Questions)

### GET `/questions`
题目模板库查询
```
Query: subject_id=1&knowledge_point_ids=15,16&type=choice&difficulty_min=2&difficulty_max=4&keyword=二次函数&page=1
```

### POST `/questions`
录入/创建题目模板
```json
// Request
{
  "subject_id": 1,
  "knowledge_point_ids": [15],
  "type": "choice",
  "difficulty": 3,
  "content": "二次函数 $y=ax^2+bx+c$ 的对称轴方程是",
  "content_latex": "二次函数 $y=ax^2+bx+c$ 的对称轴方程是",
  "options": { "A": "$x=-\\frac{b}{2a}$", "B": "$x=\\frac{b}{2a}$", "C": "$x=-\\frac{b}{a}$", "D": "$x=\\frac{2b}{a}$" },
  "answer": "A",
  "answer_latex": "$x=-\\frac{b}{2a}$",
  "explanation": "根据二次函数对称轴公式...",
  "source": "2024某某中学期中"
}
```

### POST `/questions/search-similar`
相似题检索（向量搜索）
```json
// Request
{
  "query_text": "二次函数顶点坐标计算",
  "knowledge_point_ids": [15],
  "top_k": 5
}

// Response 200
{
  "results": [
    {
      "question_id": 200,
      "content": "求 $y=2x^2-4x+1$ 的顶点坐标",
      "similarity": 0.92,
      "difficulty": 3
    }
  ]
}
```

---

## 7. 作答与判卷 (Submissions & Grading)

### GET `/exams/{exam_id}/submissions`
某考试的所有作答记录
```
Query: student_id=101&page=1
```

### GET `/submissions/{id}`
作答详情
```json
// Response 200
{
  "id": 500,
  "exam_question": {
    "id": 100,
    "sequence": 1,
    "content": "二次函数顶点坐标...",
    "score": 5
  },
  "student": { "id": 101, "real_name": "李明" },
  "answer_text": "(-1, 2)",
  "answer_image_url": null,
  "submitted_at": "2026-04-15T09:30:00Z",
  "grading_result": {
    "id": 5000,
    "is_correct": true,
    "score": 5,
    "error_type": null,
    "knowledge_point_ids": [152],
    "ai_model": "deepseek-r1",
    "confidence": 0.98,
    "teacher_override": false
  }
}
```

### POST `/submissions/{id}/grade`
对单个作答进行 AI 判卷
```json
// Request
{ "model": "deepseek-r1" }

// Response 200
{
  "grading_result_id": 5001,
  "is_correct": false,
  "score": 0,
  "error_type": "calculation_error",
  "error_type_detail": "计算顶点纵坐标时符号错误，应为 (-b²+4ac)/4a = 2",
  "knowledge_point_ids": [152],
  "confidence": 0.95
}
```

### PUT `/grading-results/{id}`
教师人工修正判卷结果
```json
// Request
{
  "is_correct": true,
  "score": 3,
  "error_type": "missing_step",
  "teacher_remark": "过程不完整，但结果正确，给一半分"
}
```

---

## 8. 学生知识模型 (Knowledge States)

### GET `/students/{id}/knowledge-states`
学生知识点掌握状态列表
```
Query: subject_id=1&mastery_max=0.6&sort_by=mastery&page=1
```
```json
// Response 200
{
  "total": 45,
  "items": [
    {
      "knowledge_point": { "id": 152, "name": "顶点坐标计算", "code": "MATH-FUNC-QUAD-01" },
      "mastery_probability": 0.35,
      "decayed_mastery": 0.28,
      "total_attempts": 12,
      "correct_count": 4,
      "last_error_type": "calculation_error",
      "last_graded_at": "2026-04-28T10:00:00Z",
      "status": "weak" // weak / normal / mastered
    }
  ]
}
```

### GET `/students/{id}/knowledge-radar`
学生知识点雷达图数据
```json
// Response 200
{
  "dimensions": [
    { "name": "函数与方程", "mastery": 0.72 },
    { "name": "几何", "mastery": 0.45 },
    { "name": "概率统计", "mastery": 0.88 }
  ]
}
```

---

## 9. 诊断报告 (Reports)

### GET `/students/{id}/reports`
学生报告列表
```
Query: report_type=exam&page=1
```

### GET `/reports/{id}`
报告详情
```json
// Response 200
{
  "id": 100,
  "student_id": 101,
  "exam_id": 10,
  "report_type": "exam",
  "title": "2026年4月期中考试诊断报告",
  "overall_comment": "本次考试整体表现良好，但二次函数相关知识点掌握不够扎实...",
  "weak_knowledge_points": [
    {
      "kp_id": 152,
      "name": "顶点坐标计算",
      "mastery": 0.35,
      "error_count": 5,
      "trend": "down" // up / down / stable
    }
  ],
  "error_type_distribution": {
    "concept_error": 3,
    "calculation_error": 8,
    "misreading": 2,
    "missing_step": 4
  },
  "mastery_trend": [
    { "date": "2026-03-01", "avg_mastery": 0.62 },
    { "date": "2026-04-15", "avg_mastery": 0.58 }
  ],
  "radar_chart_data": { ... },
  "generated_at": "2026-04-16T10:00:00Z"
}
```

### POST `/students/{id}/reports/generate`
生成诊断报告
```json
// Request
{
  "exam_id": 10,
  "report_type": "exam",
  "model": "deepseek-r1"
}

// Response 202
{ "report_id": 101, "status": "generating", "task_id": "..." }
```

---

## 10. 练习与出题 (Exercises)

### POST `/exercises/generate`
AI 生成针对性练习
```json
// Request
{
  "student_id": 101,
  "title": "二次函数薄弱点专项训练",
  "target_knowledge_point_ids": [152, 153],
  "difficulty_range": [2, 4],
  "question_types": ["choice", "short_answer"],
  "total_questions": 10,
  "model": "deepseek-r1"
}

// Response 201
{
  "id": 50,
  "status": "generating",
  "task_id": "celery-uuid",
  "estimated_seconds": 60
}
```

### GET `/exercises/{id}`
练习详情
```json
// Response 200
{
  "id": 50,
  "title": "二次函数薄弱点专项训练",
  "status": "ready",
  "student": { "id": 101, "real_name": "李明" },
  "questions": [
    {
      "id": 2000,
      "sequence": 1,
      "type": "choice",
      "content": "...",
      "difficulty": 3,
      "knowledge_points": ["顶点坐标计算"],
      "student_answer": null,
      "is_correct": null
    }
  ],
  "total_questions": 10,
  "completed_count": 0,
  "created_at": "2026-05-07T14:00:00Z"
}
```

### POST `/exercises/{id}/submit`
提交练习答案
```json
// Request
{
  "answers": [
    { "question_id": 2000, "answer_text": "A" },
    { "question_id": 2001, "answer_text": "(-2, 3)" }
  ]
}

// Response 200
{
  "submission_id": 300,
  "auto_graded": true,
  "results": [
    { "question_id": 2000, "is_correct": true, "score": 5 },
    { "question_id": 2001, "is_correct": false, "score": 0, "error_type": "calculation_error" }
  ]
}
```

---

## 11. 错题本 (Error Books)

### GET `/students/{id}/error-book`
学生错题本
```
Query: knowledge_point_id=152&error_type=calculation_error&is_reviewed=false&page=1
```
```json
// Response 200
{
  "total": 28,
  "items": [
    {
      "id": 1000,
      "question_content": "求 $y=x^2+4x+5$ 的顶点坐标",
      "student_answer": "(-4, 5)",
      "correct_answer": "(-2, 1)",
      "error_type": "calculation_error",
      "knowledge_points": ["顶点坐标计算"],
      "is_reviewed": false,
      "review_count": 0,
      "created_at": "2026-04-15T10:00:00Z",
      "similar_questions": [
        { "id": 2001, "content": "...", "similarity": 0.91 }
      ]
    }
  ]
}
```

### POST `/error-book-items/{id}/review`
标记错题已复习
```json
// Response 200
{ "review_count": 1, "last_reviewed_at": "2026-05-07T14:30:00Z" }
```

### GET `/students/{id}/error-book/export`
导出错题本 PDF
```
Query: knowledge_point_ids=152,153&from_date=2026-01-01
```
```json
// Response 200
{ "download_url": "https://minio/.../error_book_101_20260507.pdf" }
```

---

## 12. OCR 任务 (OCR Tasks)

### GET `/ocr-tasks`
OCR 任务列表
```
Query: exam_id=10&status=success&page=1
```

### GET `/ocr-tasks/{id}`
OCR 任务详情
```json
// Response 200
{
  "id": 55,
  "exam_id": 11,
  "file_url": "https://minio/.../exam_11_page1.jpg",
  "status": "success",
  "provider": "qwen-vl",
  "result_json": {
    "pages": [
      {
        "page_number": 1,
        "questions": [
          {
            "sequence": 1,
            "bbox": { "x": 120, "y": 200, "width": 600, "height": 80 },
            "content": "二次函数 $y=x^2+2x+3$ 的顶点坐标是",
            "type": "choice"
          }
        ]
      }
    ]
  },
  "completed_at": "2026-05-07T14:05:00Z"
}
```

---

## 13. AI 交互日志 (AI Interactions)

### GET `/ai-interactions`
AI 调用日志（管理员/审计）
```
Query: task_type=grading&model=deepseek-r1&from_date=2026-05-01&to_date=2026-05-07&page=1
```
```json
// Response 200
{
  "total": 1250,
  "items": [
    {
      "id": 5000,
      "task_type": "grading",
      "model": "deepseek-r1",
      "provider": "deepseek",
      "request_tokens": 1200,
      "response_tokens": 350,
      "cost_usd": 0.0032,
      "latency_ms": 2800,
      "status": "success",
      "related_exam_id": 10,
      "created_at": "2026-05-07T14:00:00Z"
    }
  ],
  "summary": {
    "total_cost_usd": 15.23,
    "total_tokens": 450000,
    "avg_latency_ms": 3200
  }
}
```

---

## 14. 通用响应规范

### 成功响应
```json
// 单对象
{ "code": 200, "message": "success", "data": { ... } }

// 列表
{ "code": 200, "message": "success", "data": { "total": 100, "items": [...] } }

// 创建成功
HTTP 201
{ "code": 201, "message": "created", "data": { "id": 1 } }

// 异步任务接受
HTTP 202
{ "code": 202, "message": "accepted", "data": { "task_id": "...", "status": "processing" } }
```

### 错误响应
```json
// 400 Bad Request
{ "code": 400, "message": "参数校验失败", "detail": [{ "field": "email", "msg": "无效的邮箱格式" }] }

// 401 Unauthorized
{ "code": 401, "message": "未认证或 Token 已过期" }

// 403 Forbidden
{ "code": 403, "message": "无权访问此资源" }

// 404 Not Found
{ "code": 404, "message": "资源不存在" }

// 422 Validation Error (FastAPI 默认)
{ "detail": [{ "loc": ["body", "email"], "msg": "invalid email", "type": "value_error" }] }

// 500 Internal Error
{ "code": 500, "message": "服务器内部错误", "trace_id": "uuid-for-debug" }
```

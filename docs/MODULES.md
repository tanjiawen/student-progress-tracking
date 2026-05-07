# 模块详细设计（Module Design）

## 模块依赖图

```
┌─────────────────────────────────────────────────────────────┐
│                        前端层 (React)                        │
│  Login │ Dashboard │ ExamUpload │ Grading │ Report │ Exercise │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ REST API / WebSocket
┌─────────────────────────────────────────────────────────────┐
│                        API 网关层                            │
│              FastAPI Router (认证/权限/校验)                  │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   同步服务层   │   │   异步任务层     │   │   AI 服务层      │
│  (FastAPI)    │   │   (Celery)      │   │  (外部 API)      │
│               │   │                 │   │                 │
│ • UserService │   │ • OcrTask       │   │ • DeepSeek      │
│ • ExamService │   │ • GradingTask   │   │ • Mathpix       │
│ • ReportSvc   │   │ • ExerciseTask  │   │ • Qwen-VL       │
│ • ClassService│   │ • ReportTask    │   │ • Embedding     │
└───────┬───────┘   └─────────────────┘   └─────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│                      数据访问层 (Repository)                  │
│         PostgreSQL │ Redis │ Qdrant │ MinIO                │
└─────────────────────────────────────────────────────────────┘
```

---

## M1. 用户与权限模块 (Auth & User)

**职责**：身份认证、角色授权、用户生命周期管理

**核心组件**：
- `AuthService`：JWT 签发/校验/刷新
- `UserService`：用户 CRUD、角色分配
- `ClassStudentService`：班级学生关联管理
- `PermissionMiddleware`：基于角色的 API 权限控制

**角色权限矩阵**：

| 功能 | admin | teacher | student | parent |
|------|:-----:|:-------:|:-------:|:------:|
| 用户管理 | ✅ | ❌ | ❌ | ❌ |
| 班级管理 | ✅ | 仅自己班 | ❌ | ❌ |
| 试卷上传 | ✅ | ✅ | ❌ | ❌ |
| 判卷审核 | ✅ | ✅ | ❌ | ❌ |
| 查看报告 | ✅ | 仅自己班学生 | 仅自己 | 仅关联孩子 |
| 在线练习 | ❌ | ❌ | ✅ | ❌ |
| 错题本 | ❌ | ❌ | ✅ | 仅关联孩子 |
| 系统配置 | ✅ | ❌ | ❌ | ❌ |

---

## M2. 知识图谱模块 (Knowledge Graph)

**职责**：维护学科-章节-知识点的层级结构与关联关系

**核心组件**：
- `KnowledgePointService`：树形 CRUD、递归查询
- `KnowledgeRelationService`：图关系维护
- `SubjectService`：学科管理

**关键技术**：
- 邻接表模型 + PostgreSQL CTE 递归查询
- 知识点编码自动生成（如 `MATH-FUNC-QUAD-01`）
- 路径查询：获取从根到某知识点的完整路径（用于报告展示）

**数据初始化策略**：
- 提供标准课标导入脚本（JSON 格式）
- 支持教师在线微调结构

---

## M3. 试卷与题目模块 (Exam & Question)

**职责**：试卷生命周期管理、题目库维护

**核心组件**：
- `ExamService`：考试创建、状态流转（draft → processing → graded → archived）
- `ExamQuestionService`：试卷题目实例化管理
- `QuestionTemplateService`：母题库 CRUD、向量入库
- `FileStorageService`：MinIO 文件上传/下载/预签名 URL

**状态机**：
```
draft ──[upload]──> processing ──[ocr_complete]──> ready ──[start_grading]──> grading ──[complete]──> graded ──[archive]──> archived
```

---

## M4. OCR 处理模块 (OCR Pipeline)

**职责**：将试卷图片/PDF 转换为结构化题目数据

**处理流程**：
```
原始图片 → 预处理（旋转/裁边/二值化） → 多模态 OCR → 结构化解析 → 人工校对 → 入库
```

**核心组件**：
- `OcrTaskService`：任务创建、状态追踪
- `MathpixClient`：公式转 LaTeX
- `QwenVLClient` / `GPT4VClient`：版式分析与手写识别
- `OcrResultParser`：将 OCR 原始输出解析为标准题对象

**降级策略**：
- Mathpix 失败 → 尝试 Qwen-VL
- 云端 API 失败 → 本地 Ollama Qwen-VL 兜底
- 置信度 < 0.7 的题目自动标记待人工校对

---

## M5. AI 判卷引擎 (Grading Engine)

**职责**：自动判断学生作答正误，分析错因，映射知识点

**输入**：
- 题干（LaTeX + 文本）
- 标准答案
- 学生作答（文本或 OCR 结果）
- 评分标准（可选）

**输出（JSON Schema）**：
```json
{
  "is_correct": false,
  "score": 2,
  "max_score": 5,
  "error_type": "calculation_error",
  "error_type_detail": "配方时漏加了常数项...",
  "knowledge_point_ids": [152, 153],
  "confidence": 0.94,
  "suggestion": "建议复习完全平方公式..."
}
```

**核心组件**：
- `GradingService`：判卷逻辑编排
- `DeepSeekClient`：大模型调用（支持 JSON Mode / Structured Output）
- `PromptTemplateManager`：判卷 Prompt 版本管理
- `ConfidenceScorer`：基于模型输出一致性评估置信度

**人工干预机制**：
- 置信度 < 0.8 的判卷结果自动进入教师审核队列
- 教师修正结果反哺：存储为 Few-shot 示例，动态拼入后续 Prompt

---

## M6. 学生知识模型模块 (Knowledge Model)

**职责**：追踪每个学生对每个知识点的掌握程度

**核心组件**：
- `KnowledgeStateService`：掌握度查询、更新
- `BKTEngine`：贝叶斯知识追踪简化实现
- `EloEngine`：ELO 变体（根据题目难度调整）
- `DecayCalculator`：时间衰减计算

**BKT 简化公式**：
```
P(L_n) = P(L_{n-1}) + (1 - P(L_{n-1})) * P(T)   [如果答对]
P(L_n) = P(L_{n-1}) * (1 - P(S))                [如果答错]

其中：
- P(L): 掌握概率
- P(T): 学习转移概率（默认 0.3）
- P(S): 失误概率（默认 0.1）
- 增加时间衰减：P_decayed = P(L) * 0.5^(days/30)
```

**掌握度分级**：
- `mastered`: >= 0.8
- `normal`: 0.4 ~ 0.8
- `weak`: < 0.4

---

## M7. 诊断报告模块 (Report Engine)

**职责**：聚合知识模型数据，生成可视化诊断报告

**核心组件**：
- `ReportService`：报告生成与查询
- `WeakPointAnalyzer`：薄弱知识点算法（综合掌握度、错误频次、知识点重要性权重）
- `TrendAnalyzer`：历次考试趋势对比
- `CommentGenerator`：AI 自然语言评语生成

**报告数据结构**：
```json
{
  "summary": { "overall_comment": "...", "total_score": 95, "rank": 5 },
  "weak_points": [...],
  "error_distribution": { "concept_error": 3, "calculation_error": 8 },
  "trend": [...],
  "radar": { "dimensions": [...], "values": [...] },
  "recommendations": [...]
}
```

---

## M8. 出题引擎模块 (Exercise Generator)

**职责**：根据薄弱知识点生成针对性训练题

**核心组件**：
- `ExerciseService`：练习卷生命周期
- `QuestionGenerator`：AI 题目生成
- `AnswerVerifier`：答案自验证
- `QuestionRetriever`：RAG 相似题检索

**出题策略**：
```
输入：目标知识点 [152, 153]，错误类型 [calculation_error]，难度 [2, 4]
步骤：
1. 从 Qdrant 检索该知识点相似经典题（Top 3）
2. 构建 Few-shot Prompt（经典题 + 生成要求）
3. 调用 LLM 生成新题（题干 + 选项 + 答案 + 解析）
4. 独立调用 LLM 验证答案正确性
5. 验证通过 → 入库；不通过 → 重试（最多 3 次）
6. 组装练习卷（基础 40% + 变式 40% + 综合 20%）
```

**题型控制**：
- 选择题：自动生成 4 个选项 + 干扰项
- 填空题：确定空格位置和答案
- 解答题：生成完整步骤和评分细则

---

## M9. 错题本模块 (Error Book)

**职责**：自动归类错题，支持复习和导出

**核心组件**：
- `ErrorBookService`：错题 CRUD、筛选、统计
- `SimilarQuestionFinder`：基于向量检索相似题
- `PdfExporter`：错题本 PDF 生成

**自动入库规则**：
- 考试判卷错误自动入库
- 练习错误自动入库
- 去重：同一知识点相似题（向量相似度 > 0.95）合并为一条，增加错误次数

---

## M10. 通知与集成模块 (Notification)

**职责**：系统事件通知，可选飞书/钉钉集成

**事件类型**：
- `exam.graded`：考试判卷完成
- `report.generated`：诊断报告生成
- `exercise.assigned`：新练习发布
- `error_book.review_due`：错题复习提醒

**集成方式**：
- Webhook 推送至飞书群/钉钉群
- 系统内消息中心（前端消息铃铛）

---

## 模块间数据流

### 核心闭环数据流

```
1. 教师上传试卷 → ExamService 创建考试记录
2. OCR Pipeline 处理 → 生成 ExamQuestions
3. 学生作答提交 → SubmissionService 创建记录
4. Grading Engine 异步判卷 → 生成 GradingResults
5. Knowledge Model 更新 → 修改 StudentKnowledgeStates
6. Report Engine 生成报告 → 存入 Reports
7. Exercise Generator 读取弱项 → 生成 Exercises
8. 学生完成练习 → 再次进入步骤 3-5，形成闭环
```

# 数据库设计（Database Design）

## 1. ER 关系图（逻辑模型）

```
users (1) ───< (N) class_students >─── (1) classes
  │                                       │
  │                                       │ 1:N
  │                                       ▼
  │                                    subjects
  │                                       │
  │                                       │ 1:N
  │                                       ▼
  │                                 knowledge_points (自关联树)
  │                                       │
  │                                       │ 1:N
  │                                       ▼
  │                                 knowledge_relations (图)
  │
  │ 1:N
  ▼
exams (1) ───< (N) exam_questions >─── (1) question_templates
  │                    │
  │                    │ N:1
  │                    ▼
  │               submissions (学生作答)
  │                    │
  │                    │ 1:1
  │                    ▼
  │               grading_results (判卷结果)
  │                    │
  │                    │ N:1 (知识点)
  │                    ▼
  │               student_knowledge_states (掌握度)
  │
  │ 1:N
  ▼
reports (诊断报告)

exercises (1) ───< (N) exercise_questions >─── (1) question_templates
  │
  │ 1:N
  ▼
error_book_items (错题本)

ocr_tasks (OCR 任务，独立)
ai_interactions (AI 调用日志，独立)
```

---

## 2. 表结构设计

### 2.1 用户与权限

```sql
-- 用户表
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    username        VARCHAR(50) NOT NULL UNIQUE,
    email           VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    real_name       VARCHAR(50) NOT NULL,
    avatar_url      VARCHAR(500),
    role            VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'teacher', 'student', 'parent')),
    phone           VARCHAR(20),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_email ON users(email);

-- 班级表
CREATE TABLE classes (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    grade       VARCHAR(20) NOT NULL,          -- 如：初一、初二、高一
    subject_id  BIGINT NOT NULL REFERENCES subjects(id),
    teacher_id  BIGINT NOT NULL REFERENCES users(id), -- 班主任/任课教师
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 班级学生关联
CREATE TABLE class_students (
    id         BIGSERIAL PRIMARY KEY,
    class_id   BIGINT NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    student_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(class_id, student_id)
);
```

### 2.2 学科与知识图谱

```sql
-- 学科表
CREATE TABLE subjects (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(50) NOT NULL,          -- 数学、物理、化学
    code        VARCHAR(20) NOT NULL UNIQUE,   -- math, physics
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 知识点表（树状结构，邻接表模型）
CREATE TABLE knowledge_points (
    id          BIGSERIAL PRIMARY KEY,
    subject_id  BIGINT NOT NULL REFERENCES subjects(id),
    parent_id   BIGINT REFERENCES knowledge_points(id), -- 自关联，根节点为 NULL
    name        VARCHAR(100) NOT NULL,
    code        VARCHAR(50) NOT NULL,          -- 唯一编码，如 MATH-JH-01-02
    level       INT NOT NULL DEFAULT 1,        -- 层级：1章 2节 3知识点
    description TEXT,
    tags        VARCHAR(100)[],                -- PostgreSQL 数组类型
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_kp_subject ON knowledge_points(subject_id);
CREATE INDEX idx_kp_parent ON knowledge_points(parent_id);
CREATE INDEX idx_kp_code ON knowledge_points(code);

-- 知识点关系表（图结构补充）
CREATE TABLE knowledge_relations (
    id          BIGSERIAL PRIMARY KEY,
    from_kp_id  BIGINT NOT NULL REFERENCES knowledge_points(id) ON DELETE CASCADE,
    to_kp_id    BIGINT NOT NULL REFERENCES knowledge_points(id) ON DELETE CASCADE,
    relation_type VARCHAR(20) NOT NULL CHECK (relation_type IN ('prerequisite', 'contains', 'related', 'extension')),
    weight      FLOAT NOT NULL DEFAULT 1.0,    -- 关系强度
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(from_kp_id, to_kp_id, relation_type)
);
CREATE INDEX idx_kr_from ON knowledge_relations(from_kp_id);
CREATE INDEX idx_kr_to ON knowledge_relations(to_kp_id);
```

### 2.3 试卷与题目

```sql
-- 考试/试卷表
CREATE TABLE exams (
    id              BIGSERIAL PRIMARY KEY,
    title           VARCHAR(200) NOT NULL,
    subject_id      BIGINT NOT NULL REFERENCES subjects(id),
    class_id        BIGINT REFERENCES classes(id), -- 可选，关联班级
    exam_date       DATE NOT NULL,
    total_score     NUMERIC(6,2) NOT NULL DEFAULT 100,
    description     TEXT,
    status          VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'processing', 'graded', 'archived')),
    created_by      BIGINT NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_exams_class ON exams(class_id);
CREATE INDEX idx_exams_status ON exams(status);

-- 题目模板表（母题库，独立于试卷）
CREATE TABLE question_templates (
    id              BIGSERIAL PRIMARY KEY,
    subject_id      BIGINT NOT NULL REFERENCES subjects(id),
    knowledge_point_ids BIGINT[] NOT NULL,     -- 关联知识点数组
    type            VARCHAR(20) NOT NULL CHECK (type IN ('choice', 'fill_blank', 'short_answer', 'proof', 'calculation')),
    difficulty      INT NOT NULL DEFAULT 3 CHECK (difficulty BETWEEN 1 AND 5), -- 1-5星
    content         TEXT NOT NULL,             -- 题干（LaTeX + 文本）
    content_latex   TEXT,                      -- 纯 LaTeX
    answer          TEXT NOT NULL,             -- 标准答案
    answer_latex    TEXT,
    explanation     TEXT,                      -- 解析
    options         JSONB,                     -- 选择题选项 {A: "...", B: "..."}
    source          VARCHAR(200),              -- 来源：2024某某中学期中
    embedding       VECTOR(1024),              -- pgvector 扩展，题目语义向量
    is_public       BOOLEAN NOT NULL DEFAULT TRUE,
    created_by      BIGINT REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_qt_subject ON question_templates(subject_id);
CREATE INDEX idx_qt_type ON question_templates(type);
CREATE INDEX idx_qt_difficulty ON question_templates(difficulty);
CREATE INDEX idx_qt_embedding ON question_templates USING ivfflat (embedding vector_cosine_ops); -- 向量索引

-- 试卷题目关联（实例化）
CREATE TABLE exam_questions (
    id              BIGSERIAL PRIMARY KEY,
    exam_id         BIGINT NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    question_template_id BIGINT REFERENCES question_templates(id), -- 可能关联母题，也可能为 NULL（新题）
    sequence        INT NOT NULL,              -- 题号顺序
    score           NUMERIC(6,2) NOT NULL DEFAULT 0,
    content         TEXT NOT NULL,             -- 实际试卷上的题干（可能有变式）
    answer          TEXT,                      -- 试卷标准答案
    ocr_raw_text    TEXT,                      -- OCR 原始文本备份
    ocr_confidence  FLOAT,                     -- OCR 置信度
    page_number     INT,                       -- 所在页码
    bbox            JSONB,                     -- 版面位置 {x, y, width, height}
    UNIQUE(exam_id, sequence)
);
CREATE INDEX idx_eq_exam ON exam_questions(exam_id);
```

### 2.4 作答与判卷

```sql
-- 学生作答记录
CREATE TABLE submissions (
    id              BIGSERIAL PRIMARY KEY,
    exam_question_id BIGINT NOT NULL REFERENCES exam_questions(id),
    student_id      BIGINT NOT NULL REFERENCES users(id),
    exam_id         BIGINT NOT NULL REFERENCES exams(id), -- 冗余，方便查询
    answer_text     TEXT,                      -- 学生答案文本
    answer_image_url VARCHAR(500),             -- 手写答案图片（OCR 结果或原图）
    is_submitted    BOOLEAN NOT NULL DEFAULT TRUE,
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(exam_question_id, student_id)
);
CREATE INDEX idx_submissions_student ON submissions(student_id);
CREATE INDEX idx_submissions_exam ON submissions(exam_id);

-- 判卷结果（核心表）
CREATE TABLE grading_results (
    id                  BIGSERIAL PRIMARY KEY,
    submission_id       BIGINT NOT NULL UNIQUE REFERENCES submissions(id),
    exam_question_id    BIGINT NOT NULL REFERENCES exam_questions(id),
    student_id          BIGINT NOT NULL REFERENCES users(id),
    is_correct          BOOLEAN NOT NULL,
    score               NUMERIC(6,2) NOT NULL DEFAULT 0,
    max_score           NUMERIC(6,2) NOT NULL,
    error_type          VARCHAR(50),           -- concept_error, calculation_error, misreading, missing_step, logic_break
    error_type_detail   TEXT,                  -- 错因详细描述
    knowledge_point_ids BIGINT[],              -- 涉及知识点
    ai_model            VARCHAR(50) NOT NULL,  -- 使用的模型 deepseek-r1, gpt-4o
    ai_raw_response     JSONB,                 -- AI 原始返回（审计）
    confidence          FLOAT NOT NULL DEFAULT 0.0, -- AI 判卷置信度
    teacher_override    BOOLEAN NOT NULL DEFAULT FALSE, -- 教师是否人工修正
    teacher_remark      TEXT,
    graded_by_ai_at     TIMESTAMPTZ,           -- AI 判卷时间
    graded_by_teacher_at TIMESTAMPTZ,          -- 教师修正时间
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_gr_student ON grading_results(student_id);
CREATE INDEX idx_gr_exam_question ON grading_results(exam_question_id);
CREATE INDEX idx_gr_error_type ON grading_results(error_type);
```

### 2.5 学生知识模型

```sql
-- 学生知识点掌握状态（BKT + ELO 混合）
CREATE TABLE student_knowledge_states (
    id                  BIGSERIAL PRIMARY KEY,
    student_id          BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    knowledge_point_id  BIGINT NOT NULL REFERENCES knowledge_points(id) ON DELETE CASCADE,
    mastery_probability FLOAT NOT NULL DEFAULT 0.5 CHECK (mastery_probability BETWEEN 0 AND 1), -- 掌握概率 P(L)
    total_attempts      INT NOT NULL DEFAULT 0,    -- 总答题次数
    correct_count       INT NOT NULL DEFAULT 0,    -- 正确次数
    consecutive_correct INT NOT NULL DEFAULT 0,    -- 连续正确次数（用于快速掌握判定）
    last_error_type     VARCHAR(50),               -- 最近一次错误类型
    last_graded_at      TIMESTAMPTZ,               -- 最近一次判卷时间
    decay_factor        FLOAT NOT NULL DEFAULT 1.0, -- 时间衰减系数
    UNIQUE(student_id, knowledge_point_id)
);
CREATE INDEX idx_sks_student ON student_knowledge_states(student_id);
CREATE INDEX idx_sks_kp ON student_knowledge_states(knowledge_point_id);
CREATE INDEX idx_sks_mastery ON student_knowledge_states(mastery_probability);
```

### 2.6 诊断报告与练习

```sql
-- 诊断报告
CREATE TABLE reports (
    id                  BIGSERIAL PRIMARY KEY,
    student_id          BIGINT NOT NULL REFERENCES users(id),
    exam_id             BIGINT REFERENCES exams(id), -- 可能基于单次考试或综合
    report_type         VARCHAR(20) NOT NULL DEFAULT 'exam' CHECK (report_type IN ('exam', 'weekly', 'monthly')),
    title               VARCHAR(200) NOT NULL,
    weak_knowledge_points JSONB,                 -- TOP 薄弱知识点 [{kp_id, name, mastery, trend}]
    error_type_distribution JSONB,               -- 错误类型分布 {concept_error: 5, ...}
    mastery_trend       JSONB,                   -- 历次掌握度趋势 [{date, avg_mastery}]
    radar_chart_data    JSONB,                   -- 雷达图数据
    overall_comment     TEXT,                    -- AI 生成的自然语言评语
    ai_model            VARCHAR(50),
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_read             BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_reports_student ON reports(student_id);
CREATE INDEX idx_reports_exam ON reports(exam_id);

-- 练习卷（AI 生成）
CREATE TABLE exercises (
    id              BIGSERIAL PRIMARY KEY,
    student_id      BIGINT NOT NULL REFERENCES users(id),
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    target_knowledge_point_ids BIGINT[],        -- 目标薄弱知识点
    difficulty_range INT[] NOT NULL DEFAULT ARRAY[1,5], -- [min, max]
    question_types  VARCHAR(20)[] NOT NULL DEFAULT ARRAY['choice', 'fill_blank', 'short_answer'],
    status          VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'generating', 'ready', 'assigned', 'completed')),
    total_questions INT NOT NULL DEFAULT 0,
    generated_by_ai BOOLEAN NOT NULL DEFAULT TRUE,
    ai_model        VARCHAR(50),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_exercises_student ON exercises(student_id);
CREATE INDEX idx_exercises_status ON exercises(status);

-- 练习题目关联
CREATE TABLE exercise_questions (
    id              BIGSERIAL PRIMARY KEY,
    exercise_id     BIGINT NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    question_template_id BIGINT REFERENCES question_templates(id), -- 可能复用母题
    sequence        INT NOT NULL,
    content         TEXT NOT NULL,             -- 实际练习中的题干
    answer          TEXT NOT NULL,
    explanation     TEXT,
    student_answer  TEXT,                      -- 学生实际作答
    is_correct      BOOLEAN,
    ai_verified     BOOLEAN NOT NULL DEFAULT FALSE, -- 答案是否经 AI 自验证
    UNIQUE(exercise_id, sequence)
);

-- 错题本
CREATE TABLE error_book_items (
    id              BIGSERIAL PRIMARY KEY,
    student_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exam_question_id BIGINT REFERENCES exam_questions(id),
    exercise_question_id BIGINT REFERENCES exercise_questions(id), -- 练习中的错题
    question_content TEXT NOT NULL,            -- 题目内容快照
    student_answer  TEXT,
    correct_answer  TEXT,
    error_type      VARCHAR(50) NOT NULL,
    knowledge_point_ids BIGINT[],
    is_reviewed     BOOLEAN NOT NULL DEFAULT FALSE, -- 是否已复习
    review_count    INT NOT NULL DEFAULT 0,
    last_reviewed_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_ebi_student ON error_book_items(student_id);
CREATE INDEX idx_ebi_error_type ON error_book_items(error_type);
CREATE INDEX idx_ebi_created ON error_book_items(created_at);
```

### 2.7 任务与日志

```sql
-- OCR 处理任务
CREATE TABLE ocr_tasks (
    id              BIGSERIAL PRIMARY KEY,
    exam_id         BIGINT NOT NULL REFERENCES exams(id),
    file_url        VARCHAR(500) NOT NULL,     -- 原始文件
    task_type       VARCHAR(20) NOT NULL DEFAULT 'full' CHECK (task_type IN ('full', 'formula', 'handwriting')),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'success', 'failed')),
    provider        VARCHAR(50) NOT NULL,      -- mathpix, qwen-vl, gpt-4v
    result_json     JSONB,                     -- OCR 结构化结果
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_ocr_exam ON ocr_tasks(exam_id);
CREATE INDEX idx_ocr_status ON ocr_tasks(status);

-- AI 调用日志（成本审计 + 效果追踪）
CREATE TABLE ai_interactions (
    id              BIGSERIAL PRIMARY KEY,
    task_type       VARCHAR(50) NOT NULL,      -- grading, exercise_generation, report, ocr
    model           VARCHAR(50) NOT NULL,      -- deepseek-r1, gpt-4o
    provider        VARCHAR(50) NOT NULL,      -- deepseek, openai, local
    request_tokens  INT NOT NULL DEFAULT 0,
    response_tokens INT NOT NULL DEFAULT 0,
    cost_usd        NUMERIC(10,6),             -- 估算成本
    latency_ms      INT NOT NULL DEFAULT 0,    -- 响应延迟
    status          VARCHAR(20) NOT NULL DEFAULT 'success',
    request_payload JSONB,                     -- 请求摘要（脱敏）
    response_summary JSONB,                    -- 响应摘要
    related_exam_id BIGINT REFERENCES exams(id),
    related_student_id BIGINT REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_ai_task ON ai_interactions(task_type);
CREATE INDEX idx_ai_model ON ai_interactions(model);
CREATE INDEX idx_ai_created ON ai_interactions(created_at);
```

---

## 3. 扩展说明

### 3.1 pgvector 扩展
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```
用于 `question_templates.embedding` 的语义向量存储与相似度检索。

### 3.2 时间衰减函数（PostgreSQL）
```sql
-- 计算知识点掌握度的时间衰减值
CREATE OR REPLACE FUNCTION calculate_decayed_mastery(
    mastery FLOAT,
    last_graded_at TIMESTAMPTZ,
    half_life_days INT DEFAULT 30
) RETURNS FLOAT AS $$
DECLARE
    days_passed FLOAT;
BEGIN
    days_passed := EXTRACT(EPOCH FROM (NOW() - last_graded_at)) / 86400.0;
    RETURN mastery * POWER(0.5, days_passed / half_life_days);
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

### 3.3 知识点树递归查询（CTE）
```sql
-- 获取某知识点及其所有后代
WITH RECURSIVE kp_tree AS (
    SELECT id, name, parent_id, level, 0 AS depth
    FROM knowledge_points
    WHERE id = ?
    UNION ALL
    SELECT kp.id, kp.name, kp.parent_id, kp.level, kt.depth + 1
    FROM knowledge_points kp
    JOIN kp_tree kt ON kp.parent_id = kt.id
)
SELECT * FROM kp_tree;
```

### 3.4 Qdrant 集合设计（向量库）

| 集合名 | 向量维度 | 距离度量 | Payload 字段 |
|--------|----------|----------|--------------|
| `question_embeddings` | 1024 | Cosine | `question_id`, `knowledge_point_ids`, `difficulty`, `type`, `subject_id` |
| `error_embeddings` | 1024 | Cosine | `error_book_item_id`, `student_id`, `knowledge_point_ids`, `error_type` |

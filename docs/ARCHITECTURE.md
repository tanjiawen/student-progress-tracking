# 系统架构设计（System Architecture）

## 1. 核心业务流程（Core Business Flow）

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  上传试卷   │ -> │  OCR解析    │ -> │  自动判卷   │ -> │ 知识模型更新 │
│ (PDF/图片)  │    │ (题目/作答) │    │ (错因分析)  │    │ (掌握度追踪) │
└─────────────┘    └─────────────┘    └─────────────┘    └──────┬──────┘
                                                                  │
┌─────────────┐    ┌─────────────┐    ┌─────────────┐           │
│  在线答题   │ <- │  针对性出题  │ <- │  诊断报告   │ <─────────┘
│ (新题训练)  │    │ (薄弱点)    │    │ (可视化)    │
└─────────────┘    └─────────────┘    └─────────────┘
```

### 业务闭环（Loop）
1. **输入**：学生试卷扫描件 → 高分辨率图片/PDF
2. **识别**：OCR + 多模态模型提取题干、公式（LaTeX）、手写作答
3. **判卷**：LLM 对照答案自动判分，输出错因类型 + 知识点映射
4. **建模**：更新学生知识掌握向量（ELO / BKT 算法）
5. **诊断**：生成薄弱知识点排行、错误类型分布、趋势对比
6. **出题**：基于薄弱点 + 错误类型生成针对性训练题（带答案验证）
7. **训练**：学生完成新题 → 再次进入判卷流程，形成持续闭环

---

## 2. 系统边界（System Boundary）

### 2.1 系统内（In-Scope）
| 模块 | 说明 |
|------|------|
| 用户与权限 | 管理员、教师、学生、家长四角色权限体系 |
| 试卷管理 | 上传、存储、分页、拆题、版本管理 |
| OCR & 版面分析 | 印刷体/手写体/公式识别，题干与作答区域分离 |
| 自动判卷引擎 | 正误判断、错因归因（概念/计算/审题/步骤/逻辑）、知识点标注 |
| 知识图谱 | 学科-章节-知识点树状结构，前置/包含/相关关系 |
| 学生知识模型 | 每个学生对每个知识点的掌握概率、错误次数、时间衰减 |
| 诊断报告 | 薄弱点 TOP5、错误类型饼图、历次考试趋势曲线、雷达图 |
| 出题引擎 | 根据薄弱点+难度+题型生成新题，答案自验证 |
| 练习管理 | 练习卷组装、派发、作答、回收 |
| 错题本 | 自动归类、相似题检索、PDF 导出 |
| 班级管理 | 多学生批量分析、班级薄弱点热力图 |
| 人工审核台 | 教师修正判卷结果和生成的题目，反馈入库 |

### 2.2 系统外（Out-of-Scope / 外部依赖）
| 依赖 | 用途 | 接入方式 |
|------|------|----------|
| DeepSeek API / OpenAI API | 大模型推理（判卷、出题） | HTTP API |
| Mathpix API | 公式转 LaTeX | HTTP API |
| Qwen-VL / GPT-4V | 多模态 OCR 与版面分析 | HTTP API / 本地部署 |
| 对象存储 (MinIO/OSS) | 试卷图片、PDF、生成文件 | S3 SDK |
| 飞书/钉钉（可选） | 消息通知推送 | Webhook |

---

## 3. 技术架构（Technical Architecture）

### 3.1 架构选型

| 层级 | 技术选型 | 理由 |
|------|----------|------|
| **前端** | React 19 + TypeScript + Ant Design 5 + ECharts | 生态成熟，TypeScript 强类型，AntD 组件丰富，ECharts 可视化强大 |
| **后端** | Python 3.12 + FastAPI + Pydantic v2 | 异步高性能，AI 生态强，自动 OpenAPI 文档，Pydantic 校验严格 |
| **数据库** | PostgreSQL 16 | ACID 强一致性，JSONB 灵活，窗口函数强大，适合知识树递归查询 |
| **向量数据库** | Qdrant | 轻量高效，Docker 单容器可跑，Rust 高性能，过滤查询友好 |
| **缓存 / 消息队列** | Redis 7 | 缓存 + Celery Broker 一体，减少组件数量 |
| **任务调度** | Celery + Flower | 异步处理 OCR/判卷/出题等耗时任务，Flower 监控任务状态 |
| **本地模型** | Ollama + vLLM | Ollama 管理本地 Qwen2.5/DeepSeek 模型；vLLM 提供高吞吐推理 |
| **容器化** | Docker + Docker Compose | 开发环境一键启动，生产可迁移至 K3s |
| **监控** | Prometheus + Grafana（二期） | 系统健康、API 延迟、模型调用成本监控 |

### 3.2 部署架构（Development）

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose Network                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  nginx   │  │  react   │  │ fastapi  │  │  celery  │   │
│  │ (reverse │  │ (static) │  │  (api)   │  │ (worker) │   │
│  │  proxy)  │  └──────────┘  └────┬─────┘  └────┬─────┘   │
│  └────┬─────┘                     │             │          │
│       └───────────────────────────┴─────────────┘          │
│                                   │                         │
│  ┌──────────┐  ┌──────────┐  ┌───┴────┐  ┌──────────┐    │
│  │postgres  │  │  redis   │  │ qdrant │  │  minio   │    │
│  │ (主库)   │  │(cache+mq)│  │(向量库) │  │(对象存储)│    │
│  └──────────┘  └──────────┘  └────────┘  └──────────┘    │
└─────────────────────────────────────────────────────────────┘

外部 API: DeepSeek API / Mathpix API / Qwen-VL API
```

### 3.3 后端模块划分（Clean Architecture）

```
backend/
├── app/
│   ├── main.py                 # FastAPI 应用入口
│   ├── core/                   # 核心配置、日志、异常、依赖注入
│   ├── api/                    # 路由层（Controller）
│   │   ├── v1/
│   │   │   ├── auth.py         # 认证
│   │   │   ├── users.py        # 用户管理
│   │   │   ├── students.py     # 学生
│   │   │   ├── teachers.py     # 教师
│   │   │   ├── exams.py        # 考试/试卷
│   │   │   ├── questions.py    # 题目
│   │   │   ├── submissions.py  # 作答记录
│   │   │   ├── knowledge.py    # 知识点
│   │   │   ├── reports.py      # 诊断报告
│   │   │   ├── exercises.py    # 练习/出题
│   │   │   ├── error_books.py  # 错题本
│   │   │   └── classes.py      # 班级
│   ├── services/               # 业务逻辑层（Service）
│   │   ├── ocr_service.py      # OCR 与版面分析
│   │   ├── grading_service.py  # 自动判卷
│   │   ├── knowledge_service.py # 知识模型更新
│   │   ├── report_service.py   # 诊断报告生成
│   │   ├── exercise_service.py # 出题引擎
│   │   └── notification_service.py # 通知
│   ├── models/                 # SQLModel / SQLAlchemy 模型
│   ├── schemas/                # Pydantic DTO
│   ├── repositories/           # 数据访问层（Repository）
│   ├── tasks/                  # Celery 异步任务
│   ├── ai/                     # AI 客户端封装
│   │   ├── deepseek.py         # DeepSeek API 客户端
│   │   ├── mathpix.py          # Mathpix API 客户端
│   │   ├── qwen_vl.py          # Qwen-VL 客户端
│   │   └── prompts/            # Prompt 模板管理
│   └── utils/                  # 工具函数
├── migrations/                 # Alembic 数据库迁移
├── tests/                      # 测试
├── celery_worker.py            # Celery 启动入口
└── Dockerfile
```

### 3.4 前端模块划分

```
frontend/
├── src/
│   ├── main.tsx                # 入口
│   ├── App.tsx                 # 路由配置
│   ├── api/                    # Axios 封装 + API 类型
│   ├── components/             # 通用组件
│   ├── pages/                  # 页面
│   │   ├── Login/
│   │   ├── Dashboard/          # 教师仪表盘
│   │   ├── ExamUpload/         # 试卷上传
│   │   ├── ExamDetail/         # 试卷详情 / 判卷结果
│   │   ├── StudentProfile/     # 学生学情画像
│   │   ├── ReportView/         # 诊断报告
│   │   ├── Exercise/           # 针对性练习
│   │   ├── ErrorBook/          # 错题本
│   │   ├── ClassManage/        # 班级管理
│   │   └── Admin/              # 后台管理
│   ├── stores/                 # Zustand 状态管理
│   ├── hooks/                  # 自定义 Hooks
│   └── utils/                  # 工具函数
└── Dockerfile
```

---

## 4. 关键算法与策略

### 4.1 知识追踪算法（Knowledge Tracing）
- **方案**：贝叶斯知识追踪（Bayesian Knowledge Tracing, BKT）简化变体
- **状态**：每个学生对每个知识点维护二元状态 {掌握, 未掌握}
- **更新**：每次答题后根据正误更新 P(掌握)，引入时间衰减因子
- **存储**：PostgreSQL JSONB 或独立表 `student_knowledge_states`

### 4.2 题目相似检索（RAG）
- **向量化**：题目文本 + LaTeX 公式 → Embedding（BGE-M3 / OpenAI text-embedding-3）
- **存储**：Qdrant 向量库，payload 携带知识点 ID、难度、题型
- **检索**：出题时根据目标知识点检索相似经典题作为 Few-shot 示例

### 4.3 答案自验证
- **方案**：生成题目后，独立调用 LLM（或代码解释器）求解
- **校验**：对比生成时的参考答案与独立求解结果
- **不一致处理**：重新生成或标记人工审核

---

## 5. 非功能需求

| 维度 | 目标 |
|------|------|
| **性能** | API 响应 < 200ms（P95），OCR/判卷异步任务 < 30s/份试卷 |
| **并发** | 支持 50 教师同时在线，Celery Worker 水平扩展 |
| **安全** | JWT 认证 + RBAC 权限，学生数据脱敏，HTTPS 全链路 |
| **可用性** | 本地 L20 + 云端 API 混合，单点故障时自动降级 |
| **扩展性** | 微服务模块化，模型可热插拔切换（配置化） |
| **数据隐私** | 敏感试卷本地处理，仅非敏感元数据可选上传云端 |

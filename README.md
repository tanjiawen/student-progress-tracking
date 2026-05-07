# Student Progress Tracking（学生学情跟踪）

> AI 驱动的学生学情分析与针对性训练系统。基于试卷 OCR、大模型自动判卷、知识图谱追踪、智能出题引擎，形成完整的学情诊断闭环。

## 版本

`0.0.1`

## 核心功能

- **试卷智能识别**：支持 PDF/图片上传，OCR + 多模态模型自动拆题、识别公式（LaTeX）
- **AI 自动判卷**：DeepSeek / GPT-4o 自动判分、错因归因、知识点映射
- **知识图谱追踪**：贝叶斯知识追踪（BKT）实时更新学生知识点掌握度
- **诊断报告**：薄弱点 TOP5、错误类型分布、历次趋势对比、AI 自然语言评语
- **针对性出题**：基于薄弱点 RAG 检索相似题 + AI 生成新题，答案自验证
- **错题本**：自动归类、相似题推荐、PDF 导出、间隔重复复习提醒
- **班级热力图**：多维度班级学情可视化，教师决策支持

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 19 + TypeScript + Vite + Ant Design 5 + ECharts |
| 后端 | Python 3.12 + FastAPI + SQLModel + Pydantic v2 |
| 数据库 | PostgreSQL 16 + Qdrant（向量库） |
| 缓存/队列 | Redis 7 + Celery |
| 对象存储 | MinIO |
| AI 模型 | DeepSeek API / OpenAI API / 本地 Ollama |
| 部署 | Docker + Docker Compose |

## 快速开始

### 环境要求

- Docker + Docker Compose
- Git

### 一键启动开发环境

```bash
# 克隆项目
git clone https://github.com/tanjiawen/student-progress-tracking.git
cd student-progress-tracking

# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps
```

服务访问地址：

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| Flower 任务监控 | http://localhost:5555 |
| MinIO 控制台 | http://localhost:9001 (minioadmin / minioadmin) |
| Qdrant | http://localhost:6333 |

### 本地开发（不依赖 Docker）

#### 后端

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 复制环境变量
cp .env.example .env
# 编辑 .env 配置数据库和 AI API Key

# 启动服务
uvicorn app.main:app --reload
```

#### 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

## 项目结构

```
student-progress-tracking/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/         # REST API 路由
│   │   ├── core/           # 配置、安全、依赖、异常
│   │   ├── models/         # SQLModel 数据模型
│   │   ├── schemas/        # Pydantic DTO
│   │   ├── services/       # 业务逻辑
│   │   ├── repositories/   # 数据访问
│   │   ├── ai/             # AI 客户端与 Prompt
│   │   └── utils/          # 工具函数
│   ├── alembic/            # 数据库迁移
│   ├── tests/              # 测试
│   ├── requirements.txt
│   ├── Dockerfile
│   └── celery_worker.py    # Celery 入口
├── frontend/                # React 前端
│   ├── src/
│   │   ├── api/            # HTTP 客户端
│   │   ├── components/     # 通用组件
│   │   ├── pages/          # 页面
│   │   ├── stores/         # Zustand 状态
│   │   ├── hooks/          # 自定义 Hooks
│   │   └── utils/          # 工具函数
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docs/                    # 设计文档
│   ├── ARCHITECTURE.md     # 系统架构
│   ├── DATABASE.md         # 数据库设计
│   ├── API_SPEC.md         # API 接口规范
│   ├── ROADMAP.md          # 开发路线图
│   └── MODULES.md          # 模块详细设计
├── docker-compose.yml       # 开发环境编排
└── README.md
```

## 设计文档

- [系统架构设计](docs/ARCHITECTURE.md) — 业务流程、技术选型、部署架构
- [数据库设计](docs/DATABASE.md) — ER 关系、14 张核心表、索引设计、向量库
- [API 接口规范](docs/API_SPEC.md) — RESTful API、请求/响应 DTO、错误码
- [开发路线图](docs/ROADMAP.md) — 7 个阶段、13 周里程碑、验收标准
- [模块详细设计](docs/MODULES.md) — 10 大模块职责、依赖关系、核心算法

## 开发阶段

| 阶段 | 周期 | 目标 |
|------|------|------|
| Phase 1 | Week 1-2 | 基础设施 + 核心数据模型 |
| Phase 2 | Week 3-4 | 用户/班级/知识图谱管理后台 |
| Phase 3 | Week 5-6 | 试卷上传 + OCR + 题目解析 |
| Phase 4 | Week 7-8 | AI 判卷引擎 + 知识模型更新 |
| Phase 5 | Week 9-10 | 诊断报告 + 出题引擎 |
| Phase 6 | Week 11-12 | 练习闭环 + 错题本 + 班级热力图 |
| Phase 7 | Week 13+ | 优化 + 监控 + 生产部署 |

## 核心算法

- **BKT 知识追踪**：贝叶斯更新学生知识点掌握概率，引入时间衰减
- **ELO 变体**：根据题目难度动态调整掌握度评分
- **RAG 出题增强**：向量检索相似经典题作为 Few-shot 示例，提升出题质量
- **答案自验证**：独立 LLM 求解对比，确保生成题目答案正确

## 贡献与许可

本项目为私有仓库，仅供内部开发使用。

## 联系方式

如有问题，请通过 GitHub Issues 或内部沟通渠道反馈。

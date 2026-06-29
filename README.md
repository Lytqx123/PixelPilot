# PixelPulse 多模态RAG知识库引擎

面向企业私有化部署的多模态RAG知识库系统，提供智能问答、权限管控、知识溯源、审核工作流等企业级功能。

***

## 支持的文档格式

| 格式类型   | 支持扩展名             | 解析方式                 |
| ---------- | ---------------------- | ------------------------ |
| PDF 文档   | `.pdf`                 | PyPDF2 / unstructured    |
| Word 文档  | `.docx`                | python-docx              |
| Excel 表格 | `.xlsx`                | openpyxl                 |
| 图片文件   | `.png/.jpg/.jpeg/.bmp` | PaddleOCR / VLM 视觉理解 |
| CAD 图纸   | `.dxf`                 | ezdxf 专用解析器         |
| 纯文本     | `.txt/.md`             | 直接读取                 |

> ✅ 注：CAD 图纸解析目前支持 DXF 格式，DWG 格式需额外转换工具支持。

***

## 技术栈

### 后端技术

- **Web 框架**: FastAPI 0.104.1
- **ORM**: SQLAlchemy 2.0 (asyncpg 异步驱动)
- **数据库迁移**: Alembic 1.13.0
- **数据校验**: Pydantic 2.7.0
- **认证**: python-jose (JWT) + passlib + bcrypt
- **关系数据库**: PostgreSQL 16
- **向量数据库**: Qdrant v1.7.4
- **缓存/队列**: Redis 7
- **文档解析**: unstructured, PaddleOCR, ezdxf
- **HTTP 客户端**: httpx (异步连接池)

### 前端技术

- **框架**: Vue 3.4
- **构建工具**: Vite 5.0
- **UI 组件库**: Element Plus 2.4
- **状态管理**: Pinia 2.1
- **路由**: Vue Router 4.2
- **HTTP 客户端**: Axios 1.6
- **Markdown 渲染**: markdown-it 14.0

### AI 模型（通过 Ollama 部署）

| 用途      | 模型                | 说明            |
| ------- | ----------------- | ------------- |
| 对话/总结   | qwen2.5:14b       | 主力大语言模型       |
| 文本向量化   | bge-m3            | 多语言向量模型，1024维 |
| 图纸/图片理解 | minicpm-v:8b      | 多模态视觉模型       |
| 检索重排    | Qwen3-Reranker-4B | 检索结果精排        |

> ✅ 注：Reranker 和 VLM 为可选功能，可通过配置文件禁用。

### 部署

- **容器化**: Docker + Docker Compose
- **Web 服务器**: Nginx (前端静态托管 + API 反向代理)
- **Python 版本**: 3.11
- **Node 版本**: 20

***

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        浏览器客户端                          │
│                     (Vue 3 + Element Plus)                  │
└────────────────────────────┬────────────────────────────────┘
                             │ :3000
┌────────────────────────────▼────────────────────────────────┐
│                     Nginx (Frontend)                        │
│         静态文件托管 / API反向代理 / SSE流式支持             │
└────────────────────────────┬────────────────────────────────┘
                             │
         ┌───────────────────┴───────────────────┐
         │                                       │
┌────────▼─────────┐                   ┌─────────▼────────┐
│  Backend (API)   │                   │  Worker (后台)    │
│    FastAPI       │◄─────────────────►│  文档解析/向量化  │
│  认证/业务逻辑    │     Redis队列      │  定时任务清理     │
└────────┬─────────┘                   └─────────┬────────┘
         │                                       │
         ├───────────────────┬───────────────────┤
┌────────▼─────────┐ ┌───────▼────────┐ ┌────────▼────────┐
│   PostgreSQL     │ │     Redis      │ │     Qdrant      │
│  业务数据存储     │ │  缓存/任务队列  │ │  向量语义检索    │
└──────────────────┘ └────────────────┘ └─────────────────┘
         ▲
         │
┌────────┴─────────┐
│  Ollama (宿主机)  │
│  LLM/Embedding   │
└──────────────────┘
```

### 服务说明

| 服务         | 端口    | 说明           | 资源建议                     |
| ---------- | ----- | ------------ | ------------------------ |
| Frontend   | 3000  | Web 前端入口     | 0.5 CPU / 256MB          |
| Backend    | 8000  | FastAPI 后端服务 | 2 CPU / 1GB              |
| Worker     | -     | 后台任务处理       | 2 CPU / 1.5GB            |
| PostgreSQL | 5432  | 关系型数据库       | 1 CPU / 512MB            |
| Redis      | 6379  | 缓存/消息队列      | 0.5 CPU / 384MB          |
| Qdrant     | 6333  | 向量数据库        | 1.5 CPU / 1GB            |
| Ollama     | 11434 | AI 模型服务      | 4+ CPU / 8GB+ 内存（需GPU更佳） |

> ✅ 注：以上为最低配置建议，生产环境请根据文档量和并发量适当扩容。

***

## 快速开始

### 前置要求

- Docker 20.10+
- Docker Compose v2+
- [Ollama](https://ollama.com/) 运行在宿主机（用于AI模型推理）
- 至少 8GB 可用内存（模型加载建议 16GB+）

***

### 方式一：Docker Compose 部署（推荐）

#### 1. 克隆项目并进入目录

```bash
cd pixelpulse
```

#### 2. 配置环境变量

复制环境变量模板并根据实际情况修改：

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

```bash
# Linux/macOS
cp .env.example .env
```

**生产环境必须修改** **`SECRET_KEY`** 为随机字符串。

#### 3. 拉取并启动 Ollama 模型

确保 Ollama 服务已启动（默认端口 11434），然后拉取所需模型：

```bash
ollama pull qwen2.5:14b
ollama pull bge-m3
ollama pull minicpm-v:8b       # 可选：多模态理解
ollama pull dengcao/Qwen3-Reranker-4b  # 可选：检索重排
```

#### 4. 启动所有服务

```bash
docker compose up -d --build
```

#### 5. 执行数据库迁移

首次启动需要执行数据库迁移创建表结构：

```bash
docker compose exec -T backend alembic upgrade head
```

#### 6. 初始化基础数据

创建默认管理员账号和系统配置：

```bash
docker compose exec -T backend python scripts/init_db.py
```

#### 7. 访问系统

打开浏览器访问：**<http://localhost:3000>**

使用默认账号登录（见 [默认账号](#默认账号) 章节）。

## 默认账号

执行初始化脚本后，系统会创建以下默认账号：

| 角色    | 用户名     | 密码         | 说明     |
| ----- | ------- | ---------- | ------ |
| 超级管理员 | `admin` | `admin123` | 拥有所有权限 |

> ⚠️ **重要提示**：首次登录后请立即修改默认密码！

### 角色体系说明

| 角色            | 权限范围                     |
| ------------- | ------------------------ |
| `SUPER_ADMIN` | 超级管理员，系统所有功能，包括系统设置、用户管理 |
| `ADMIN`       | 管理员，用户管理、审核、审计日志查看       |
| `REVIEWER`    | 审核员，文档审核、访问申请审批          |
| `USER`        | 普通用户，文档查询、问答、收藏、申请权限     |

***

## API 文档

启动后端服务后，可通过以下地址访问交互式 API 文档：

- **Swagger UI**: <http://localhost:8000/docs>
- **ReDoc**: <http://localhost:8000/redoc>
- **健康检查**: <http://localhost:8000/api/health>

### 主要 API 模块

| 模块    | 前缀               | 说明                  |
| ----- | ---------------- | ------------------- |
| 认证管理  | `/api/auth`      | 登录、登出、获取当前用户信息      |
| 超级管理员 | `/api/admin`     | 用户管理、系统设置、审计日志、向量索引 |
| 审核工作流 | `/api/review`    | 文档审核、访问申请审批         |
| 智能问答  | `/api/knowledge` | 对话管理、SSE 流式问答、对话历史  |
| 文档管理  | `/api/documents` | 上传、列表、详情、下载、收藏、标签   |
| 数据导出  | `/api/export`    | 审计日志导出              |

***

## Ollama 模型准备

### 安装 Ollama

访问 [Ollama 官网](https://ollama.com/) 下载并安装对应操作系统版本。

### 拉取模型

```bash
# 主力模型（必需）
ollama pull qwen2.5:14b
ollama pull bge-m3

# 可选模型
ollama pull minicpm-v:8b        # 图纸/图片理解
ollama pull dengcao/Qwen3-Reranker-4b  # 检索重排（提升问答准确度）
```

### 验证 Ollama 运行

```bash
curl http://localhost:11434/api/tags
```

> ✅ 注：如果不需要处理图片/CAD图纸，可以不拉取 minicpm-v 模型并在 `.env` 中设置 `VISION_ENABLED=false`；如果机器性能有限，可以设置 `RERANKER_ENABLED=false` 禁用重排。

### 硬件建议

| 模型                | 参数量  | 显存/内存建议               |
| ----------------- | ---- | --------------------- |
| qwen2.5:14b       | 14B  | 8GB+ 显存（量化）或 16GB+ 内存 |
| bge-m3            | 568M | 2GB+ 内存               |
| minicpm-v:8b      | 8B   | 8GB+ 显存               |
| Qwen3-Reranker-4B | 4B   | 4GB+ 显存或 8GB+ 内存      |

> ✅ 注：没有 GPU 的环境也可运行，模型会自动使用 CPU 推理，但响应速度会较慢。

***

## 常见问题

### Q1: 启动后后端日志提示 SECRET\_KEY 错误？

A: 生产环境必须修改 `.env` 中的 `SECRET_KEY` 为随机字符串。开发环境可在 `.env` 中添加 `ALLOW_DEFAULT_SECRET=1` 跳过校验。

### Q2: Docker 容器内无法连接宿主机 Ollama？

A: docker-compose.yml 已配置 `extra_hosts` 将 `host.docker.internal` 指向宿主机网关。确保 Ollama 监听 `0.0.0.0:11434` 而非仅 `127.0.0.1`。设置环境变量：

```bash
# Linux
OLLAMA_HOST=0.0.0.0 ollama serve
```

### Q3: 文档上传后长时间处于"解析中"状态？

A: 检查 Worker 容器日志：

```bash
docker compose logs -f worker
```

常见原因：

- PaddleOCR 首次运行需要下载模型，请耐心等待
- Ollama 服务未启动或模型未拉取
- 内存不足导致 Worker 进程被 OOM kill

### Q4: 问答响应很慢？

A:

1. 检查是否启用了 Reranker 和 VLM，可按需禁用
2. 减小 `CHUNK_SIZE`、`RERANKER_PREFETCH`、`RERANKER_TOP_K` 参数
3. 确保 Ollama 使用 GPU 加速
4. 换用更小参数的模型（如 qwen2.5:7b）

### Q5: 如何重置数据库？

A:

```bash
# 停止服务并删除数据卷（注意：会清除所有数据！）
docker compose down -v
# 重新启动并迁移
docker compose up -d --build
docker compose exec -T backend alembic upgrade head
docker compose exec -T backend python scripts/init_db.py
```

### Q6: 支持的最大文件大小是多少？

A: Nginx 配置默认最大上传为 200MB。如需修改，请调整 `frontend/nginx.conf` 中的 `client_max_body_size` 后重新构建前端镜像。

***

## 运维命令

### 服务管理

```bash
# 启动所有服务（后台运行）
docker compose up -d --build

# 停止所有服务
docker compose down

# 重启某个服务
docker compose restart backend

# 查看服务日志
docker compose logs -f backend
docker compose logs -f worker
```

### 数据库操作

```bash
# 执行迁移
docker compose exec -T backend alembic upgrade head

# 创建新迁移
docker compose exec backend alembic revision --autogenerate -m "migration message"

# 初始化数据
docker compose exec -T backend python scripts/init_db.py

# 进入数据库容器
docker compose exec postgres psql -U postgres -d pixelpulse
```

### 进入容器

```bash
# 进入后端容器
docker compose exec backend /bin/sh

# 进入 Worker 容器
docker compose exec worker /bin/sh
```

### 备份与恢复

```bash
# 备份 PostgreSQL
docker compose exec -T postgres pg_dump -U postgres pixelpulse > backup.sql

# 恢复 PostgreSQL
cat backup.sql | docker compose exec -T postgres psql -U postgres -d pixelpulse

# 备份上传文件
docker run --rm -v pixelpulse_rag_uploads:/data -v ${PWD}:/backup alpine tar czf /backup/uploads.tar.gz -C /data .
```

***

## 评测数据集与性能指标

基于企业内部真实智驾领域文档构建评测集，涵盖PDF技术文档、工程图纸(DWG/DXF)、测试规范等多类型数据，对系统各模块进行量化评测。

### 性能对比

| 指标 | 传统ES关键词检索 | 基础RAG(bge-m3) | PixelPulse(完整方案) | 提升幅度 |
|------|----------------|----------------|---------------------|---------|
| **Recall@7** | 32.0% | 78.1% | **91.8%** | +53% (vs基础RAG) |
| **MRR** | 0.32 | 0.67 | **0.81** | +153% (vs ES) |
| **回答准确率** | --(无生成能力) | 76.4% | **90.6%** | -- |
| **首字延迟(TTFT)** | <0.1s | 1.2s | 1.7s | 可接受范围内 |
| **图纸检索Recall@5** | -- | 22.0%(仅OCR) | **71.4%(OCR+VLM)** | +224% (vs OCR) |

### 消融实验

| 实验配置 | Recall@7 | Precision@7 | 首字延迟 |
|---------|---------|------------|---------|
| 仅向量检索(bge-m3) | 78.1% | 64.2% | 1.1s |
| 向量+关键词混合(RRF) | 82.5% | 68.7% | 1.2s |
| **混合+Reranker(完整方案)** | **91.8%** | **88.3%** | 1.7s |

**结论**：每一层叠加都产生正向增益，Reranker引入是收益最大的单模块优化（Precision+28.5%），代价是延迟增加0.5s，ToB场景下可接受。

### Bad Case归因分析

| Bad Case类型 | 占比 | 根因分析 | 优化方向 | 优先级 |
|-------------|------|---------|---------|-------|
| 跨文档推理断裂 | 33% | 当前检索基于单片段相似度，无法理解文档间逻辑关联 | 引入知识图谱，检索结果中增加关联文档推荐 | P1 |
| 图纸微小文字漏识别 | 27% | 渲染DPI=600对6pt字号不够，PaddleOCR对小字号识别率约65% | 增大渲染DPI到1200；引入超分辨率预处理 | P1 |
| 版本混淆 | 20% | 缺少文档版本管理机制，未标记版本号和生效状态 | 增加document_versions表，检索时默认取最新生效版本 | P0 |
| 特定术语OOD | 13% | bge-m3预训练语料以通用领域为主，企业内部缩写属于OOD词汇 | 构建企业术语词典，检索时自动展开缩写 | P2 |
| LLM幻觉/事实错误 | 5% | Prompt约束不足，缺少事实性校验环节 | 增加事实性校验，每个数字须标注来源 | P2 |
| 其他(截断/编码等) | 2% | 边界工程问题 | 增加上下文长度管理，统一字符编码处理 | P3 |

### 分块策略优化

| Chunk Size | Overlap | Recall@7 | 回答完整度(1-5) | 结论 |
|-----------|---------|---------|---------------|------|
| 256 | 50 | 54.2% | 2.4 | 分块过小，语义断裂严重 |
| 512 | 100 | 68.4% | 3.2 | 不适用于智驾长段落文档 |
| 800 | 150 | 78.1% | 3.8 | 接近最优区间 |
| **1000** | **200** | **86.7%** | **4.3** | **采用方案**：完整覆盖知识单元 |
| 1500 | 300 | 82.3% | 4.1 | 大Chunk引入噪声，Recall下降 |

### 模型选型

**Embedding模型**：

| 模型 | 维度 | Recall@5 | 是否采用 | 理由 |
|------|------|---------|---------|------|
| bge-m3 (BAAI) | 1024 | 78.1% | ✅ | 多语言+长文本检索专用，中文术语召回率高 |
| text2vec-large-chinese | 1024 | 71.3% | ❌ | 长文本衰减严重 |
| OpenAI text-embedding-3-large | 3072 | 66.0% | ❌ | 违反数据本地化要求 |
| bge-small-zh | 512 | 64.5% | ❌ | 维度太低 |

**Reranker模型**：

| Reranker | Precision@7 | 延迟增量 | 是否采用 | 理由 |
|----------|------------|---------|---------|------|
| Qwen3-Reranker-4B | 94.6% | +0.9s | ✅ | 中文Reranker SOTA，本地推理 |
| 无Reranker | 62.3% | 0s | ❌ | 精确率不达标 |
| Cohere Rerank v3 | 91.2% | +0.3s | ❌ | 云端API，违反数据本地化 |
| bge-reranker-v2-m3 | 87.5% | +0.6s | ❌ | 效果略低 |

**图纸解析方案**：

| 方案 | 信息覆盖率 | 图纸检索Recall@5 | 是否采用 | 理由 |
|------|-----------|-----------------|---------|------|
| 仅ezdxf文本提取 | 31.2% | 22.0% | ❌ | 语义丢失严重 |
| **OCR+VLM(minicpm-v:8b)** | **78.5%** | **71.4%** | ✅ | 文字提取+结构语义理解 |
| 仅PaddleOCR | 42.3% | 35.1% | ❌ | 无结构理解 |
| GPT-4V(云端) | 85.0% | 75%+ | ❌ | 违反数据本地化 |

### 模型选型总览

| 用途 | 模型名称 | 参数/维度 | 部署平台 |
|------|---------|----------|---------|
| 主力对话 | qwen2.5:14b | 14B | Ollama |
| 文本嵌入 | bge-m3 (BAAI) | 1024维 | Ollama |
| 视觉理解(VLM) | minicpm-v:8b | 8B | Ollama |
| 重排序(Reranker) | Qwen3-Reranker-4B | 4B | Ollama |
| 备选轻量嵌入 | bge-small-zh | 512维 | Ollama |

***

## 开发说明

### 新增迁移版本

后端模型修改后，需要生成新的 Alembic 迁移：

```bash
cd backend
alembic revision --autogenerate -m "描述本次变更"
alembic upgrade head
```

### 代码规范

- 后端：遵循 PEP 8，使用 Python 类型注解
- 前端：遵循 Vue 3 Composition API 风格

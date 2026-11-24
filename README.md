# Bale Knowledge

Bale Knowledge 是一个基于 Flask、Vue、LangChain 和 Milvus 的文档检索问答项目。它支持文档上传、文本切分、向量化、相似度检索、带参考来源的生成回答，并提供可脱离 Web 框架使用的检索契约和应用服务。

当前版本已完成基础上传安全、Milvus 集合操作修复以及领域服务解耦。项目仍采用同步文档入库和单向量检索，适合本地开发、协议集成和小规模知识库实验。

## 核心特性

- **文档入库**：通过 multipart 上传文件，完成加载、递归切分、Embedding 和 Milvus 写入。
- **多格式加载**：TXT、PDF、CSV 使用当前显式依赖即可处理；DOC/DOCX/XLS/XLSX 通过 LangChain 可选加载器接入，需安装相应额外依赖。
- **向量检索**：Milvus 使用 COSINE 度量和 HNSW 索引，返回真实相似度分数，并按阈值过滤。
- **生成问答**：通过 OpenAI-compatible API 生成回答，同时返回检索内容、元数据和分数。
- **独立检索契约**：`Retriever.search()` 和 `SearchHit` 不依赖 Flask、Milvus 或 LangChain，可供其他 Python 调用方使用。
- **服务化分层**：Ingestion、Retrieval、Generation 和 Collection Service 与外部 SDK 适配器分离。
- **可测试性**：提供 `FakeRetriever`、共享异步契约测试、Service 测试和 Flask API 回归测试。
- **Vue 界面**：提供文档上传、集合选择、问答和参考来源展示。

## 当前功能边界

以下能力尚未实现，不应按现有功能依赖：

- SQL 元数据数据库、原始文件对象存储和文档版本管理。
- 异步 Ingest Worker、幂等键、任务租约和失败恢复。
- BM25、RRF、Neural Rerank 或混合检索。
- 结构化 Metadata/ACL Filter；新 `filters` 参数的真实 Milvus 路径会显式返回 `NotImplementedError`。
- 严格证据拒答、标准化 Citation、TokenBudget 和忠实度评测。
- 用户认证、权限审批、多租户隔离和生产级 API 安全策略。
- FastAPI、Dockerfile、Docker Compose 和自动化前端测试。

当前问答在缺少相关资料时仍可能使用通用模型知识回答，不应将其视为严格知识库限定模式。

## 技术栈

| 层 | 当前实现 |
|---|---|
| 语言 | Python，推荐 3.11 |
| 后端 | Flask 3.1.3、Flask-Cors 6.0.5 |
| 领域契约 | Python `dataclass`、`Protocol`、`asyncio` |
| 文档与切分 | LangChain Community/Core、RecursiveCharacterTextSplitter |
| 向量数据库 | Milvus，通过 `pymilvus==3.0.3` 和 `langchain-milvus==0.4.0` 访问 |
| Embedding | DashScope Embedding；代码保留 HuggingFace 备用初始化路径 |
| 生成模型 | OpenAI SDK 3.58.0，兼容 OpenAI-style Base URL |
| 前端 | Vue 3、Vite 7、Element Plus、Axios、Markdown-it |
| Node | `^20.19.0 || >=22.12.0` |
| 测试 | pytest、pytest 集成 smoke、ReportLab PDF 测试工具 |

具体版本以 `requirements.txt`、`requirements-dev.txt` 和 `frontend/package.json` 为准。

## 项目结构

```text
bale-knowledge/
├── backend/
│   ├── adapters/
│   │   ├── legacy_documents.py   # 复用现有加载和切分逻辑
│   │   └── openai_generator.py   # OpenAI-compatible 生成适配器
│   ├── domain/
│   │   ├── models.py             # Chunk、SearchHit、Answer
│   │   ├── ports.py              # 文档、向量存储和生成端口
│   │   ├── retriever.py          # 异步 Retriever 契约
│   │   └── testing.py            # FakeRetriever
│   ├── services/
│   │   ├── ingestion.py          # 入库编排
│   │   ├── retrieval.py          # 同步/异步检索与阈值过滤
│   │   ├── generation.py         # 检索上下文和答案编排
│   │   └── collections.py        # 集合信息与清空
│   ├── stores/
│   │   └── vector.py             # Milvus VectorStore 适配器
│   ├── api_integration.py        # Flask HTTP Adapter
│   ├── composition.py            # 具体依赖组合根
│   ├── vector_db_manager.py      # 现有 LangChain/Milvus 底层实现
│   ├── vector_retriever.py       # 旧 Python API 兼容门面
│   └── server.py                 # Flask 开发服务器入口
├── frontend/
│   ├── src/components/RagChat.vue
│   ├── package.json
│   └── vite.config.js
├── tests/                        # 单元、契约、API 与 Milvus smoke
├── docs/
│   ├── architecture.md
│   └── quickstart.md
├── .env.example
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## 快速启动

后端最小安装流程：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example backend/.env
```

编辑 `backend/.env`，配置 Milvus、Embedding 和生成模型，然后启动：

```bash
python -m backend.server
```

正常启动需要可连接的 Milvus 和可用的 Embedding Provider。Milvus 安装、完整环境变量、上传/检索示例、前端启动和故障排查见[快速启动指南](docs/quickstart.md)。

## API 概览

所有向量接口使用 `/api/vector` 前缀。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/upload_file` | multipart 上传并同步入库 |
| POST | `/search` | 返回相似度检索结果 |
| POST | `/query` | 检索并生成带参考来源的回答 |
| GET | `/collection_info` | 查询指定集合信息 |
| POST | `/clear_collection` | 显式清空指定集合 |
| GET | `/` | Flask 根路径状态文本 |

上传限制为 20 MiB；允许的扩展名为 `.txt`、`.pdf`、`.csv`、`.docx`、`.doc`、`.xlsx`、`.xls`。集合清空接口没有认证保护，不应直接暴露在不受信网络中。

## Python 检索接口

```python
import asyncio

from backend.composition import create_services

services = create_services()
hits = asyncio.run(
    services.retrieval.search(
        "如何配置向量数据库？",
        namespace="agent_rag",
        top_k=5,
    )
)

for hit in hits:
    print(hit.score, hit.content, hit.metadata)
```

`namespace` 在当前 Milvus 适配器中映射为集合名称。异步接口通过线程执行同步向量调用；独立脚本可以使用 `asyncio.run()`，Flask 请求路径使用同步 `search_sync()`，不得在请求处理函数中嵌套启动事件循环。

## 测试与验证

```bash
python -m pytest -q
python -m pip check
```

默认测试不依赖真实 Milvus，集成 smoke 会跳过。启动 Milvus 后可显式执行：

```bash
MILVUS_INTEGRATION=1 python -m pytest -q tests/test_milvus_smoke.py
```

前端依赖安装与构建：

```bash
cd frontend
npm ci
npm run build
```

## 开发与贡献

1. 通过 Issue 描述问题、复现步骤、环境版本和预期行为；外部服务问题请附上去敏后的错误信息。
2. 创建主题分支，保持修改聚焦，并遵循现有 Python/ Vue 代码风格。
3. 领域层和 Service 不得新增 Flask、Milvus、LangChain 或 OpenAI SDK 依赖；外部实现应放在 Adapter 中。
4. 修改公开契约时，同步更新 `FakeRetriever`、共享契约测试和调用方说明。
5. 修改 API 时必须保留或明确变更请求/响应结构，并补充 Flask 回归测试。
6. 提交前运行后端测试、`pip check`；涉及前端时运行 `npm run build`。
7. 不提交 `backend/.env`、密钥、运行时集合数据、缓存、`node_modules/` 或构建产物。
8. Pull Request 中说明设计动机、验证结果、兼容性和尚未覆盖的限制。

## 许可证

当前仓库尚未指定开源许可证，也未包含 `LICENSE` 文件。在维护者明确选择许可证之前，本仓库不授予额外的复制、修改或再分发许可。添加许可证后，以根目录 `LICENSE` 文件为准。

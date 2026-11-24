# Bale Knowledge 快速启动指南

本指南覆盖后端、Milvus、可选 Vue 前端和基础 API 的本地运行流程。当前上传与索引在请求内同步执行，请先准备可连接的 Milvus 和可用的 Embedding Provider，再启动后端。

## 1. 环境要求

| 依赖 | 要求 | 是否必需 |
|---|---|---|
| Python | 推荐 3.11 | 必需 |
| pip | 当前稳定版本 | 必需 |
| Milvus Standalone | 与 `pymilvus==3.0.3` 兼容，可访问 19530 端口 | 后端运行必需 |
| Embedding Provider | 默认 DashScope API Key 与可用模型 | 正常入库/检索必需 |
| OpenAI-compatible LLM | Base URL、模型和 API Key | 问答必需，纯检索可不调用 |
| Node.js / npm | `^20.19.0 || >=22.12.0` | 仅前端需要 |
| Docker | 可用于安装 Milvus | 可选，本项目未提供 Compose 文件 |

默认模型通过远端 API 运行，不需要 GPU。若进入 HuggingFace 备用模型路径，CPU 可以运行，但可能需要额外依赖、模型下载和不同向量维度配置。

## 2. 安装后端依赖

进入项目根目录：

```bash
cd bale-knowledge
```

使用 `venv`：

```bash
python -m venv .venv
source .venv/bin/activate
```

或使用 Conda：

```bash
conda create -n bale-knowledge python=3.11 -y
conda activate bale-knowledge
```

安装运行和测试依赖：

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip check
```

`requirements-dev.txt` 包含运行依赖、pytest 和 PDF 测试工具。只部署运行环境时可使用 `requirements.txt`。

## 3. 配置环境变量

复制示例配置：

```bash
cp .env.example backend/.env
```

注意：应用读取的是 `backend/.env`，不是项目根目录的 `.env`。

| 变量 | 示例/默认值 | 说明 |
|---|---|---|
| `MILVUS_HOST` | `127.0.0.1` | Milvus 主机 |
| `MILVUS_PORT` | `19530` | Milvus gRPC 端口 |
| `COLLECTION_NAME` | `agent_rag` | 默认集合名称 |
| `EMBEDDING_MODEL` | `text-embedding-v1` | DashScope Embedding 模型 |
| `DASHSCOPE_API_KEY` | 无默认值 | 同时用于默认 Embedding 和 LLM 客户端认证 |
| `LLM_BASE_URL` | DashScope compatible-mode URL | OpenAI-compatible Base URL |
| `LLM_MODEL` | `qwen-plus` | 生成模型名称 |
| `FLASK_HOST` | `127.0.0.1` | Flask 监听地址 |
| `FLASK_PORT` | `5000` | Flask 端口 |
| `FLASK_DEBUG` | `False` | 是否启用 Flask Debug |

不要将真实 `backend/.env` 或 API Key 提交到 Git。更换 Base URL 时，应确认该服务接受当前认证方式和 OpenAI-compatible Chat Completions 请求。

配置读取顺序、Embedding 备用路径、集合维度约束和前端地址修改见[配置参考](configuration.md)。

## 4. 准备并检查 Milvus

本仓库目前不包含 Docker Compose、Milvus 配置文件或自动安装脚本。请按照 [Milvus 官方 Standalone 安装文档](https://milvus.io/docs/install_standalone-docker-compose.md)启动兼容版本，或由现有基础设施提供 Milvus 地址。

Milvus 的 MinIO 等内部依赖由所选部署方案管理，应用只连接 `MILVUS_HOST:MILVUS_PORT`。

安装完成后，在项目根目录执行：

```bash
python - <<'PY'
import os

from dotenv import load_dotenv
from pymilvus import connections, utility

load_dotenv("backend/.env")
connections.connect(
    "default",
    host=os.getenv("MILVUS_HOST", "127.0.0.1"),
    port=os.getenv("MILVUS_PORT", "19530"),
)
print("Milvus connection OK")
print("collections:", utility.list_collections())
PY
```

如果连接失败，先解决地址、端口、服务健康状态或兼容性问题，不要通过删除已有集合绕过。

## 5. 启动 Flask 后端

```bash
python -m backend.server
```

初始化过程会创建 Embedding Provider、执行一次 Embedding 验证并连接 Milvus。正常启动后检查根路径：

```bash
curl http://127.0.0.1:5000/
```

预期返回：

```text
RAG Backend Service is Running!
```

该命令使用 Flask 自带开发服务器，仅用于本地开发。`FLASK_DEBUG=True` 会启用调试行为，不应暴露到不受信网络。

## 6. 上传并检索示例文档

创建临时示例文件：

```bash
cat > /tmp/bale-knowledge-sample.txt <<'EOF'
Bale Knowledge 使用 Milvus 保存文档向量。
检索接口返回 SearchHit，其中包含内容、元数据和相似度分数。
生成问答与独立检索由不同的应用服务负责。
EOF
```

上传并同步入库：

```bash
curl -X POST http://127.0.0.1:5000/api/vector/upload_file \
  -F "collection_name=agent_rag" \
  -F "file=@/tmp/bale-knowledge-sample.txt"
```

成功响应包含 `success`、`message` 和 `database_info`。上传接口限制为 20 MiB，支持 TXT、PDF、CSV，以及安装了相应可选 Loader 依赖的 DOC/DOCX/XLS/XLSX。

执行纯检索，不调用生成模型：

```bash
curl -X POST http://127.0.0.1:5000/api/vector/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SearchHit 包含什么？",
    "collection_name": "agent_rag",
    "k": 3
  }'
```

返回的 `results` 包含：

- `content`：检索到的文本块；
- `metadata`：来源等元数据；
- `score`：COSINE 相似度分数。

默认相似度阈值为 0.5，低于阈值的结果会被过滤。

## 7. 执行生成问答

```bash
curl -X POST http://127.0.0.1:5000/api/vector/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "独立检索接口返回什么？",
    "collection_name": "agent_rag",
    "k": 3
  }'
```

响应包含 `answer`、`question_type` 和 `sources`。`sources` 是生成时使用的检索证据，不包含额外的答案置信度。

当前提示词允许模型在缺少相关资料时使用通用知识，因此不能把每次回答都视为严格限定于知识库内容的答案。

## 8. 查询或清空集合

查询集合：

```bash
curl "http://127.0.0.1:5000/api/vector/collection_info?collection_name=agent_rag"
```

显式清空集合：

```bash
curl -X POST http://127.0.0.1:5000/api/vector/clear_collection \
  -H "Content-Type: application/json" \
  -d '{"collection_name": "agent_rag"}'
```

**清空会删除该集合及其中的数据，且当前接口没有认证或审批保护。仅在确认集合名称和数据不再需要时执行。**

## 9. 使用独立 Python Retriever

以下示例只检索，不调用生成模型：

```bash
python - <<'PY'
import asyncio

from backend.composition import create_services

services = create_services()
hits = asyncio.run(
    services.retrieval.search(
        "SearchHit 包含什么？",
        namespace="agent_rag",
        top_k=3,
    )
)

for hit in hits:
    print({"content": hit.content, "score": hit.score, "metadata": hit.metadata})
PY
```

`namespace` 在当前实现中映射为 Milvus 集合名。真实 RetrievalService 暂不支持非空结构化 `filters`；如需使用旧 `filter_expression`，只能通过现有兼容入口，不应假设结构化过滤已经生效。

## 10. 启动 Vue 前端（可选）

确认 Node.js 满足 `frontend/package.json` 的 engines 要求，然后执行：

```bash
cd frontend
npm ci
npm run dev
```

Vite 默认地址通常为 `http://localhost:5173`。前端当前将 API 地址固定为 `http://localhost:5000/api/vector`，并通过 Flask-Cors 跨域访问，不依赖 Vite 代理。

如果修改了后端地址或端口，需要同步调整 `frontend/src/components/RagChat.vue` 中的 `API_BASE`。

生产模式构建与预览：

```bash
npm run build
npm run preview
```

## 11. 运行测试

后端默认测试：

```bash
python -m pytest -q
python -m pip check
```

默认情况下真实 Milvus smoke 会跳过。启动 Milvus 后显式运行：

```bash
MILVUS_INTEGRATION=1 python -m pytest -q tests/test_milvus_smoke.py
```

该 smoke 使用固定维度的测试 Embedding，创建随机临时集合并验证写入、检索和清空，不需要调用真实 Embedding API。

前端修改后至少运行：

```bash
cd frontend
npm run build
```

## 12. 常见问题排查

### 启动时无法连接 Milvus

- 用第 4 节脚本分别验证主机和端口。
- 检查 Milvus 是否健康、19530 是否映射到本机，以及防火墙/容器网络是否可达。
- 确认 `backend/.env` 被修改，而不是只修改了 `.env.example`。

### DashScope 认证或 Embedding 调用失败

- 检查 `DASHSCOPE_API_KEY`、模型名称、账户额度和网络访问。
- 启动时的模型验证失败会进入 HuggingFace 备用路径；这可能带来额外下载和依赖问题，不应忽略原始错误。
- 不要对同一个已有集合混用不同维度或不同模型的向量。

### HuggingFace 备用模型下载慢或维度不兼容

优先修复显式配置的 DashScope Provider。若确需本地模型，应单独安装对应依赖、确认向量维度，并为新配置使用新集合，不能原地混写。

### 检索有结果但回答生成失败

检查 `LLM_BASE_URL`、`LLM_MODEL` 和 API Key。纯 `/search` 不依赖生成模型，可用来区分检索问题与生成问题。

### 上传返回 400 或 413

- 400：检查 multipart 字段名必须为 `file`，以及扩展名是否在白名单中。
- 413：请求超过 20 MiB，请压缩或拆分输入。
- Office 文件还需安装相应 Loader 的可选依赖；扩展名被允许不代表所有解析依赖已经安装。

### 上传成功后检索不到内容

- 确认请求中的 `collection_name` 与上传时一致。
- 检查文档是否实际产生非空文本块。
- 相似度阈值默认是 0.5，可检查原始分数和查询表达，不要直接把零结果当作集合为空。

### 前端无法连接后端

- 确认 Flask 正在 `localhost:5000` 监听。
- 检查浏览器控制台中的 CORS 或网络错误。
- 若使用其他地址，修改前端 `API_BASE`，不要只调整 Vite 端口。

### 端口被占用

修改 `backend/.env` 中的 `FLASK_PORT`，同时更新前端 API 地址和 curl 示例；前端端口可通过 Vite 命令行参数调整。

## 13. 本地维护建议

- 定期执行默认测试；只有实际启用 Milvus smoke 后，才把集成状态标记为已验证。
- 不提交密钥、临时上传文件、模型缓存、前端依赖和构建产物。
- 对公开接口、环境变量或目录职责的修改，应同步更新[架构设计](architecture.md)和 [README](../README.md)。
- 按目标选择后续阅读：[文档索引](README.md)、[配置参考](configuration.md)、[API 参考](api.md)、[开发与测试](development.md)。

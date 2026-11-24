# 配置参考

本页说明 Bale Knowledge 的配置读取方式、全部环境变量、Embedding/生成模型约束，以及前端与测试相关配置。安装和可复制命令见[快速启动](quickstart.md)。

## 1. 配置来源与优先级

应用通过 `python-dotenv` 读取 **`backend/.env`**，不是项目根目录的 `.env`：

- [`backend/server.py`](../backend/server.py)、[`backend/api_integration.py`](../backend/api_integration.py) 和 [`backend/vector_db_manager.py`](../backend/vector_db_manager.py) 都按包内路径加载该文件。
- `load_dotenv()` 默认不覆盖已存在的进程环境变量，因此优先级为：

```text
进程环境变量 > backend/.env > 代码默认值
```

- `create_services()` 的显式参数（`milvus_host`、`milvus_port`、`embedding_model`、`dashscope_api_key`）优先于上述两者，适合测试或嵌入式调用。
- `.gitignore` 已忽略 `.env` 与 `.env.*`（仅保留 `.env.example`）；不要提交真实密钥。
- 修改配置后需要重启 Flask 进程；当前没有热加载。

从样例创建配置：

```bash
cp .env.example backend/.env
```

## 2. 环境变量总表

| 变量 | 默认值 | 作用 |
|---|---|---|
| `MILVUS_HOST` | `127.0.0.1` | Milvus 主机 |
| `MILVUS_PORT` | `19530` | Milvus gRPC 端口 |
| `COLLECTION_NAME` | `agent_rag` | `VectorDatabaseManager` 的默认集合名 |
| `EMBEDDING_MODEL` | `text-embedding-v1` | DashScope Embedding 模型 |
| `DASHSCOPE_API_KEY` | 空 | 默认 Embedding 认证，同时被生成适配器复用为 LLM Key |
| `LLM_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | OpenAI 兼容生成端点 |
| `LLM_MODEL` | `qwen-plus` | 生成模型名 |
| `FLASK_HOST` | 代码默认 `0.0.0.0`；`.env.example` 为 `127.0.0.1` | Flask 监听地址 |
| `FLASK_PORT` | `5000` | Flask 端口 |
| `FLASK_DEBUG` | `False` | 是否启用 Flask Debug |

注意两处容易误判的行为：

- **上传接口的默认集合是字面量 `agent_rag`**，不是 `COLLECTION_NAME`。若修改了 `COLLECTION_NAME`，上传时仍应显式传 `collection_name`，否则内容会写入 `agent_rag`。
- **`FLASK_HOST` 未设置时回退到 `0.0.0.0`**（监听所有网卡）。本地开发建议在 `backend/.env` 中显式写 `127.0.0.1`。

## 3. Embedding 与生成模型

### 3.1 默认 DashScope

```dotenv
MILVUS_HOST=127.0.0.1
MILVUS_PORT=19530
COLLECTION_NAME=agent_rag
EMBEDDING_MODEL=text-embedding-v1
DASHSCOPE_API_KEY=sk-...
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=False
```

应用启动时会执行一次 Embedding 验证，并连接 Milvus：Milvus 连接失败会终止启动；Embedding 失败会记录错误并回退到 HuggingFace（见下文），应修复原始错误而不是依赖回退。处理步骤见[快速启动 §12](quickstart.md#12-常见问题排查)，不要通过删除集合绕过。

### 3.2 更换生成模型

生成适配器只读取 `DASHSCOPE_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`：

```dotenv
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
DASHSCOPE_API_KEY=sk-...   # 这里仍承载 LLM Key
```

**当前实现没有独立的 `LLM_API_KEY`**，所以即使换用其他生成服务，也必须把对应 Key 写进 `DASHSCOPE_API_KEY`；同一个变量仍用于 Embedding。

### 3.3 Embedding 备用路径

DashScope 初始化或验证失败时，Manager 会记录错误并回退到 HuggingFace `sentence-transformers/all-MiniLM-L6-v2`（CPU）：

- 该路径可能需要额外依赖与模型下载，首次启动会明显变慢。
- 备用模型维度与 DashScope 模型不同（常见为 384 维 vs 1536 维），**不能与既有集合混写**。
- 这是故障兜底，不是透明的生产高可用切换；应优先修复显式配置。

### 3.4 集合与向量维度

- 新集合使用 COSINE 度量与 HNSW 索引（`M=16`、`efConstruction=200`）。
- 集合维度由首次写入时的 Embedding 模型决定。更换 `EMBEDDING_MODEL` 后，必须写入新集合，或显式清空旧集合后重建。
- `namespace` 在 Milvus 适配器中直接映射为集合名；集合不存在时检索返回空结果，而不是自动创建。
- 同一集合重复上传没有去重或版本控制，同一文件多次上传会产生重复块。

## 4. 入库与检索参数

以下参数不是环境变量，而是构造参数或固定实现：

| 参数 | 当前值 | 位置 | 说明 |
|---|---|---|---|
| `chunk_size` | `500` | `VectorDatabaseManager` 构造参数 | 递归切分块大小 |
| `chunk_overlap` | `50` | `VectorDatabaseManager` 构造参数 | 切分重叠 |
| `similarity_threshold` | `0.5` | `RetrievalService` 构造参数 | 低于阈值的结果被过滤 |
| `top_k` | 请求参数，默认 `5` | HTTP/Service | 不做范围校验，建议传正整数 |
| `filters` | 未实现 | `RetrievalService.search_sync` | 非空结构化过滤直接抛 `NotImplementedError` |
| `filter_expression` | 旧兼容路径 | HTTP 请求体 | 原样传给 Milvus 表达式，不是通用过滤语言 |

如需调整切分参数，应在组合根或测试中显式构造 Manager；当前没有对应的环境变量入口。

## 5. HTTP 与前端配置

后端：

```dotenv
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=False
```

前端当前把 API 地址写死在 [`frontend/src/components/RagChat.vue`](../frontend/src/components/RagChat.vue) 的 `API_BASE`（`http://localhost:5000/api/vector`）。修改后端地址或端口时，需要同步修改该常量并重新构建：

```bash
cd frontend
npm ci
npm run build
```

前端只调用上传与问答接口；检索、集合信息与清空接口需要通过 curl 或 Python 调用。

HTTP 当前没有认证、限流或集合级 ACL，且 CORS 对所有来源开放。只应在本机或可信内网运行；清空集合接口没有审批保护。

## 6. 测试配置

| 变量 | 作用 |
|---|---|
| `MILVUS_INTEGRATION=1` | 启用真实 Milvus smoke 测试；未设置时跳过 |
| `MILVUS_HOST` / `MILVUS_PORT` | smoke 测试连接地址，默认 `127.0.0.1:19530` |

smoke 测试使用固定 16 维测试 Embedding 和随机临时集合，不调用真实 Embedding API：

```bash
MILVUS_INTEGRATION=1 python -m pytest -q tests/test_milvus_smoke.py
```

## 7. 启动失败与排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `Connecting to Milvus` 后抛错 | 地址、端口、服务未启动或版本不兼容 | 用快速启动 §4 的连接脚本验证 |
| DashScope 验证失败并出现 HuggingFace 警告 | Key、模型名、额度或网络异常 | 修复 DashScope 配置；不要把回退当作成功 |
| 启动成功但上传返回 500 | Loader 依赖缺失、文件解析失败或集合维度冲突 | 查看后端 stderr；确认 Office 可选依赖 |
| 检索分数异常低或为空 | 查询与文档无词义/向量相似性，或阈值 0.5 过滤 | 检查原始分数与集合是否一致 |
| 前端请求被 CORS 或网络拦截 | API 地址写死为 `localhost:5000` | 修改 `API_BASE` 并重启 Vite |

完整排错清单见[快速启动 §12](quickstart.md#12-常见问题排查)。

修改环境变量、端口或模型后，应同步更新本页、[快速启动](quickstart.md)、[README](../README.md)与[架构设计](architecture.md)。

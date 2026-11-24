# HTTP API 与 Python 接口

本页是 Bale Knowledge 的接口参考，覆盖 Flask 路由、请求/响应字段、错误语义，以及脱离 Web 框架使用的 Python 服务与检索契约。本地运行步骤见[快速启动](quickstart.md)。

## 1. 通用约定

- 基础前缀：`http://<host>:<port>/api/vector`
- 请求与响应均为 JSON（上传接口为 `multipart/form-data`）。
- 成功响应包含 `"success": true`；业务失败通常返回 `"success": false` 与 `message`。
- 当前**没有认证、授权、限流或集合级 ACL**，CORS 对所有来源开放，只应在本机或可信内网使用。
- `collection_name` 对应 Milvus 集合名。集合不存在时检索返回空结果，不会自动创建。
- 检索结果默认经过相似度阈值 `0.5` 过滤；`score` 是向量相似度，不是答案置信度。

## 2. 接口总览

| 方法 | 路径 | 用途 | 认证 |
|---|---|---|---|
| `POST` | `/upload_file` | 上传文档并同步入库 | 无 |
| `POST` | `/search` | 相似度检索，不调用生成模型 | 无 |
| `POST` | `/query` | 检索并生成带来源的回答 | 无 |
| `GET` | `/collection_info` | 查询集合信息 | 无 |
| `POST` | `/clear_collection` | 清空（删除）集合 | 无 |
| `GET` | `/` | 服务状态文本 | 无 |

## 3. 上传文档

```http
POST /api/vector/upload_file
Content-Type: multipart/form-data
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file` | 文件 | 是 | 单个文件，扩展名必须在白名单内 |
| `collection_name` | 字符串 | 否 | 默认字面量 `agent_rag`，不是 `COLLECTION_NAME` 配置 |

允许的扩展名：`.txt`、`.pdf`、`.csv`、`.docx`、`.doc`、`.xlsx`、`.xls`。Office 格式还需要安装对应 Loader 的可选依赖。

```bash
curl -X POST http://127.0.0.1:5000/api/vector/upload_file \
  -F "collection_name=agent_rag" \
  -F "file=@sample.txt"
```

成功响应：

```json
{
  "success": true,
  "message": "文件上传并处理成功: sample.txt",
  "database_info": {
    "milvus_host": "127.0.0.1",
    "milvus_port": "19530",
    "collection_name": "agent_rag",
    "is_initialized": true,
    "document_count": 12
  }
}
```

处理语义：

- 文件保存到独立临时目录，成功或失败后都会清理。
- 加载 → 递归切分 → Embedding → 写入 Milvus 全部在请求内同步完成。
- 未产生任何文本块时返回 500（`文件处理失败`）。
- 没有去重：同一文件重复上传会产生重复块。

| 状态码 | 触发条件 |
|---|---|
| `400` | 服务未初始化、缺少 `file` 字段、文件名为空、扩展名不在白名单 |
| `413` | `Content-Length` 超过 20 MiB |
| `500` | 解析、切分、Embedding 或写入失败 |

## 4. 相似度检索

```http
POST /api/vector/search
Content-Type: application/json
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `query` | 字符串 | 是 | 查询文本 |
| `collection_name` | 字符串 | 是 | 目标集合 |
| `k` | 整数 | 否 | 候选数量，默认 `5`；不做范围校验 |
| `filter_expression` | 字符串 | 否 | 旧兼容路径，原样传给 Milvus 表达式 |

```bash
curl -X POST http://127.0.0.1:5000/api/vector/search \
  -H "Content-Type: application/json" \
  -d '{"query": "SearchHit 包含什么？", "collection_name": "agent_rag", "k": 3}'
```

成功响应：

```json
{
  "success": true,
  "query": "SearchHit 包含什么？",
  "results": [
    {
      "content": "检索返回内容、元数据和相似度分数。",
      "metadata": {"source": "sample.txt"},
      "score": 0.83
    }
  ]
}
```

- 结果先按 Milvus 相似度返回，再由 `RetrievalService` 过滤低于 `0.5` 的命中。
- 结构化 `filters` 未在 HTTP 暴露；`filter_expression` 只用于旧接口兼容，不适合作为不受信用户的通用过滤语言。
- 该接口不调用生成模型，可用于区分「检索问题」与「生成问题」。

| 状态码 | 触发条件 |
|---|---|
| `400` | 服务未初始化、缺少 `query` 或 `collection_name` |
| `500` | Milvus 查询或表达式执行失败 |

## 5. 生成问答

```http
POST /api/vector/query
Content-Type: application/json
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `question` | 字符串 | 是 | 用户问题 |
| `collection_name` | 字符串 | 是 | 检索目标集合 |
| `k` | 整数 | 否 | 检索条数，默认 `5` |
| `filter_expression` | 字符串 | 否 | 旧兼容过滤表达式 |

```bash
curl -X POST http://127.0.0.1:5000/api/vector/query \
  -H "Content-Type: application/json" \
  -d '{"question": "独立检索接口返回什么？", "collection_name": "agent_rag", "k": 3}'
```

成功响应：

```json
{
  "success": true,
  "question": "独立检索接口返回什么？",
  "answer": "独立检索接口返回 SearchHit，包含内容、元数据和相似度分数。",
  "question_type": "通用查询",
  "sources": [
    {
      "content": "检索接口返回 SearchHit……",
      "metadata": {"source": "sample.txt"},
      "score": 0.81
    }
  ]
}
```

语义说明：

- 上下文按 `参考资料1`、`参考资料2` 拼接；没有命中时向模型传 `(无)`。
- 系统提示允许模型在资料不足时使用通用知识，并在开头声明。因此**回答不保证限定在知识库内容内**。
- 生成或检索异常会被 `GenerationService` 捕获，返回 HTTP 200、`success: true`，但 `answer` 是错误文本、`question_type` 为 `错误`、`sources` 为空。排查时应检查 `question_type`，不能只看 `success`。

| 状态码 | 触发条件 |
|---|---|
| `400` | 服务未初始化、缺少 `question` 或 `collection_name` |
| `500` | 请求处理中未被服务层捕获的异常 |

## 6. 集合信息与清空

### 6.1 查询集合信息

```http
GET /api/vector/collection_info?collection_name=agent_rag
```

```bash
curl "http://127.0.0.1:5000/api/vector/collection_info?collection_name=agent_rag"
```

响应：

```json
{
  "success": true,
  "database_info": {
    "milvus_host": "127.0.0.1",
    "milvus_port": "19530",
    "collection_name": "agent_rag",
    "is_initialized": true,
    "document_count": 12
  }
}
```

- `document_count` 来自 `Collection.num_entities`，读取前会 `flush()`。
- 集合不存在时 `document_count` 为 `0`；获取统计失败时 `database_info` 可能包含 `error` 字段。
- 缺少 `collection_name` 返回 400。

### 6.2 清空集合

```http
POST /api/vector/clear_collection
```

```bash
curl -X POST http://127.0.0.1:5000/api/vector/clear_collection \
  -H "Content-Type: application/json" \
  -d '{"collection_name": "agent_rag"}'
```

**该操作会删除整个 Milvus 集合及其中数据，不可撤销，且没有认证或审批保护。** 仅在确认集合不再需要时执行。

| 状态码 | 响应 |
|---|---|
| `200` | `{"success": true, "message": "集合 'agent_rag' 已清空"}` |
| `400` | 服务未初始化或缺少 `collection_name` |
| `404` | `{"success": false, "message": "集合 'agent_rag' 不存在"}` |
| `500` | 删除失败 |

## 7. 根路径

```bash
curl http://127.0.0.1:5000/
```

返回纯文本 `RAG Backend Service is Running!`，可用于确认 Flask 进程已启动；它不代表 Milvus 或模型可用。

## 8. Python 服务接口

服务层不依赖 Flask，可直接在脚本、测试或其他调用方中使用：

```python
from backend.composition import create_services

services = create_services()

# 同步检索（Flask 请求路径使用）
hits = services.retrieval.search_sync(
    "如何配置向量数据库？",
    namespace="agent_rag",
    top_k=5,
)
for hit in hits:
    print(hit.score, hit.content, hit.metadata)

# 生成问答
answer = services.generation.answer(
    "独立检索接口返回什么？",
    namespace="agent_rag",
    top_k=5,
)
print(answer.answer, answer.question_type, len(answer.sources))
```

### 8.1 异步 Retriever 契约

`Retriever` 是供 Bale 等外部调用方依赖的最小协议：

```python
import asyncio

from backend.composition import create_services

services = create_services()
hits = asyncio.run(
    services.retrieval.search(
        "SearchHit 包含什么？",
        namespace="agent_rag",
        top_k=5,
    )
)
```

- 异步接口通过 `asyncio.to_thread` 调用同步 Milvus 客户端。
- 独立脚本可以使用 `asyncio.run()`；**Flask 请求处理函数内不得嵌套启动事件循环**，应调用 `search_sync()`。
- 非空 `filters` 会抛 `NotImplementedError`；当前只支持 `namespace`、`top_k` 和旧 `filter_expression`。
- `FakeRetriever` 提供内存实现，支持 namespace 与 metadata 等值过滤，便于确定性测试。

### 8.2 返回模型

| 类型 | 字段 | 说明 |
|---|---|---|
| `SearchHit` | `content`、`score`、`namespace`、`metadata`、`source`、`chunk_id`、`document_id` | 检索证据；`score` 不是置信度 |
| `Answer` | `answer`、`question_type`、`sources` | 生成结果及其检索来源 |
| `Chunk` | `content`、`metadata` | 待写入向量存储的文本块 |

领域模型位于 [`backend/domain/models.py`](../backend/domain/models.py)，端口定义位于 [`backend/domain/ports.py`](../backend/domain/ports.py)。

## 9. 限制与兼容性

- 上传在请求内同步完成，大文件会占用请求线程；没有异步任务或进度查询。
- 没有幂等键、文档版本、SQL 元数据或对象存储；重复上传与失败重试可能产生重复数据。
- `filter_expression` 是底层表达式透传，不是安全的用户过滤语言。
- 清空集合不可逆，也没有审计记录。
- 接口结构变更时应同步更新本页、[快速启动](quickstart.md)、[README](../README.md)与 Flask 回归测试。

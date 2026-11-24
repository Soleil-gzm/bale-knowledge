# 开发与测试指南

本页面向修改 Bale Knowledge 的开发者，说明本地开发流程、分层约束、测试矩阵、扩展方式与提交前检查。系统设计见[架构设计](architecture.md)，运行步骤见[快速启动](quickstart.md)。

## 1. 本地开发环境

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example backend/.env
```

- 推荐 Python 3.11；依赖版本以 `requirements.txt`、`requirements-dev.txt` 为准。
- 运行应用需要可连接的 Milvus 与可用的 Embedding Provider；**默认测试不需要**，真实 Milvus smoke 默认跳过。
- 前端需要 Node.js `^20.19.0 || >=22.12.0`。

## 2. 分层约束

依赖方向必须保持为：

```text
Flask Adapter / Python Caller
        ↓
应用服务（Ingestion / Retrieval / Generation / Collection）
        ↓
领域模型与端口（models / ports / retriever）
        ↑
适配器（DocumentProcessor / VectorStore / AnswerGenerator）
        ↑
LangChain · Milvus · OpenAI SDK
```

规则：

1. `backend/domain` 只使用 Python 标准库，不得导入 Flask、Milvus、LangChain 或 OpenAI SDK。
2. `backend/services` 只依赖领域模型与端口，不导入具体适配器或外部 SDK。
3. 外部 SDK 只出现在 `backend/adapters`、`backend/stores` 与 `backend/vector_db_manager.py`。
4. Flask Adapter 只做请求校验、DTO 序列化与服务调用，不直接导入 Milvus Manager。
5. 具体实现只在 [`backend/composition.py`](../backend/composition.py) 组装；不要在模块内创建全局单例。

领域层与 Service 的独立导入由 `tests/test_domain_contracts.py` 通过屏蔽外部模块的子进程检查强制执行。

## 3. 测试

### 3.1 命令

```bash
python -m pytest -q
python -m pip check
```

默认测试完全离线：不连接 Milvus、不调用 Embedding/LLM API。

真实 Milvus smoke：

```bash
MILVUS_INTEGRATION=1 python -m pytest -q tests/test_milvus_smoke.py
```

smoke 使用固定 16 维测试 Embedding 和随机临时集合，验证写入、检索与清空的完整生命周期，结束时清理集合。未实际运行该 smoke 时，不要把 Milvus 集成标记为已验证。

### 3.2 测试矩阵

| 文件 | 覆盖内容 |
|---|---|
| `tests/test_domain_contracts.py` | 领域/服务在无框架、无 SDK 环境下可导入；`FakeRetriever` 契约 |
| `tests/test_retriever_contract.py` | Fake 与真实 `RetrievalService` 共享 namespace、Top-K、顺序与空结果用例 |
| `tests/test_services.py` | 入库、阈值、生成、异常与集合委托 |
| `tests/test_document_ingestion.py` | 文档加载、切分与空内容行为 |
| `tests/test_adapters.py` | Chunk/Document/SearchHit 转换与配置传递 |
| `tests/test_composition.py` | 组合根装配与依赖替换 |
| `tests/test_api_uploads.py` | Flask 上传边界：扩展名、大小、临时文件清理 |
| `tests/test_collection_lifecycle.py` | Flask 集合信息与清空语义 |
| `tests/test_retrieval.py` | 检索适配与阈值行为 |
| `tests/test_milvus_smoke.py` | 真实 Milvus 生命周期（显式启用） |

### 3.3 编写测试的约定

- **Fake 优先**：单元测试使用内存端口或 `FakeRetriever`，不要为每个用例启动 Milvus。
- **临时目录**：文件类测试使用 pytest `tmp_path`，不要写入仓库。
- **确定性**：不依赖真实时间、网络、模型输出或全局单例。
- **契约共享**：Fake 与真实实现应运行同一组行为断言，避免 Fake 掩盖实现差异。
- **真实依赖显式开关**：新增集成测试时沿用 `MILVUS_INTEGRATION=1` 这类显式开关，并保证失败后清理临时集合。

## 4. 常见扩展方式

### 4.1 新增向量后端

1. 实现 `VectorStore` 的 `add`、`search`、`info`、`clear`。
2. 保持 `Chunk` 输入与 `SearchHit` 输出契约；`score` 必须仍是相似度，不是置信度。
3. 在 `composition.py` 注册新实现，Service 与 Flask Adapter 不应感知后端类型。
4. 复用 `tests/test_retriever_contract.py` 的契约断言，并补充后端特有测试。

### 4.2 替换文档加载或切分

实现 `DocumentProcessor.load_and_split(file_path) -> list[Chunk]`，把页码、标题等定位信息放入 `metadata`。上传接口与 Service 不需要修改。

### 4.3 替换生成模型

实现 `AnswerGenerator.generate(question, context) -> str`，在组合根注入。生成替换不得改变检索接口或 `SearchHit.score` 的语义。

### 4.4 修改公开契约

`Retriever.search()` 或 `SearchHit` 变化时，必须同步：

1. `backend/domain/testing.py` 的 `FakeRetriever`；
2. `tests/test_retriever_contract.py` 的共享断言；
3. README、[API 参考](api.md)与调用方示例；
4. 旧兼容门面 `backend/vector_retriever.py`（如仍对外提供）。

### 4.5 新增 HTTP 接口

1. 在 Flask Adapter 中完成参数校验与错误码映射；
2. 只调用应用服务，不直接访问 Milvus；
3. 补充 Flask 回归测试，覆盖成功、400 与异常路径；
4. 同步更新[API 参考](api.md)与 README 的接口表。

### 4.6 前端修改

```bash
cd frontend
npm ci
npm run dev     # 本地开发
npm run build   # 提交前构建验证
```

前端当前没有自动化组件测试；修改 `RagChat.vue` 后至少执行一次生产构建，并手动验证上传、问答与错误提示。API 地址是硬编码常量，改动后端端口时同步修改。

## 5. 编码与仓库约定

- 遵循现有风格：领域模型使用 `dataclass`，端口使用 `Protocol`，类型标注保持完整。
- 新增依赖前先确认能否复用标准库或现有依赖；运行依赖写入 `requirements.txt`，测试依赖写入 `requirements-dev.txt`。
- 不提交 `backend/.env`、密钥、`node_modules/`、`dist/`、缓存、临时上传文件或 Milvus 数据。
- 提交信息保持单一主题；行为变化、兼容性影响和验证命令写入 Pull Request 说明。

## 6. 提交前检查

```bash
python -m pytest -q
python -m pip check
```

涉及前端：

```bash
cd frontend
npm run build
```

涉及 Milvus 适配或真实集成时，额外执行：

```bash
MILVUS_INTEGRATION=1 python -m pytest -q tests/test_milvus_smoke.py
```

修改环境变量、接口、分层职责或目录结构时，同步更新 README、[配置参考](configuration.md)、[API 参考](api.md)、[快速启动](quickstart.md)与[架构设计](architecture.md)。

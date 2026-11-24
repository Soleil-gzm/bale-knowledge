# Bale Knowledge 文档索引

Bale Knowledge 是一个基于 Flask、Vue、LangChain 与 Milvus 的文档检索问答项目：上传文档后完成加载、切分、Embedding 与写入，检索时返回带相似度分数的 `SearchHit`，问答时结合检索证据与 OpenAI 兼容模型生成回答。领域模型、应用服务与外部 SDK 适配器已经解耦，可以脱离 Web 框架单独调用检索。

当前实现是**同步入库 + 单路向量检索**，适合本地开发、协议集成与小规模知识库实验；异步 Worker、混合检索、文档版本与认证授权尚未实现。完整能力与边界见[根 README](../README.md)。

## 按目标选择阅读路径

| 目标 | 先读 | 再读 |
|---|---|---|
| 本地跑通上传与问答 | [快速启动 §1–7](quickstart.md#1-环境要求) | [配置参考](configuration.md) |
| 配置 Milvus、Embedding 与生成模型 | [配置参考](configuration.md) | [快速启动 §3–4](quickstart.md#3-配置环境变量) |
| 调用 HTTP 接口 | [API 参考](api.md) | [快速启动 §6–8](quickstart.md#6-上传并检索示例文档) |
| 在其他 Python 项目中使用检索 | [API 参考 §8](api.md#8-python-服务接口) | [架构设计 §4](architecture.md#4-模块划分与核心组件) |
| 理解分层与扩展点 | [架构设计](architecture.md) | [开发与测试](development.md) |
| 修改代码或提交 PR | [开发与测试](development.md) | [架构设计 §9–10](architecture.md#9-安全与可靠性设计) |
| 前端联调 | [快速启动 §10](quickstart.md#10-启动-vue-前端可选) | [配置参考 §5](configuration.md#5-http-与前端配置) |

## 文档清单

| 文档 | 内容 | 主要读者 |
|---|---|---|
| [README](../README.md) | 项目定位、核心特性、功能边界、技术栈、项目结构与 API 概览 | 所有人 |
| [quickstart.md](quickstart.md) | 安装、环境变量、Milvus 检查、上传/检索/问答示例、前端与排错 | 首次使用者 |
| [configuration.md](configuration.md) | 配置读取与优先级、环境变量总表、模型与集合约束、前端与测试配置 | 部署者、接入方 |
| [api.md](api.md) | HTTP 路由、请求/响应字段、错误语义、Python 服务与异步 Retriever | 接入方、调用方 |
| [architecture.md](architecture.md) | 分层架构、领域契约、数据流、存储与索引、扩展点、安全与测试架构 | 贡献者、评审者 |
| [development.md](development.md) | 本地开发、分层规则、测试矩阵、扩展方式与提交前检查 | 贡献者 |

## 写作与维护约定

- **状态显式**：区分「已实现」「未实现」「仅兼容保留」；目标设计不能写成现状。
- **命令可复制**：给出前置条件、命令和预期输出；失败路径写入[快速启动 §12](quickstart.md#12-常见问题排查)。
- **证据带边界**：检索分数是相似度，不是答案置信度；不把单次实验外推为生产结论。
- **安全默认**：示例不含密钥；涉及清空集合、上传限制和无认证接口时必须标注风险。
- **同步更新**：修改环境变量、HTTP 路由、领域契约、分层职责或目录结构时，同时更新 README、本索引与对应文档。

## 相关入口

- 配置样例：[.env.example](../.env.example)
- 依赖版本：[requirements.txt](../requirements.txt)、[requirements-dev.txt](../requirements-dev.txt)、[frontend/package.json](../frontend/package.json)
- Flask 路由实现：[backend/api_integration.py](../backend/api_integration.py)
- 组合根：[backend/composition.py](../backend/composition.py)
- 领域模型与端口：[backend/domain/models.py](../backend/domain/models.py)、[backend/domain/ports.py](../backend/domain/ports.py)

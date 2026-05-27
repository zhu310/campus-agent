# API 接口说明

本文档记录当前后端主要接口。后端基于 FastAPI，启动后可访问 Swagger：

```text
http://localhost:8000/docs
```

默认后端地址：

```text
http://localhost:8000
```

## 1. 健康检查

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 根路径状态信息 |
| GET | `/health` | 健康检查 |

## 2. Dashboard

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/dashboard/summary` | 获取首页统计摘要 |

## 3. 文档与知识库

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/documents` | 获取文档列表 |
| GET | `/api/documents/{document_id}` | 获取文档详情 |
| DELETE | `/api/documents/{document_id}` | 删除文档 |
| POST | `/api/documents/upload` | 上传 PDF、DOCX、TXT、图片等文件 |
| POST | `/api/documents/index-text` | 直接写入文本并建立索引 |
| POST | `/api/knowledge/index` | 将文档内容写入知识库 |

## 4. RAG 问答

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat/ask` | 兼容问答接口 |
| POST | `/api/chat/query` | RAG 问答接口 |
| POST | `/api/chat/query-stream` | 流式问答接口 |

建议演示问题：

```text
单人能否参赛？
报名截止时间是什么？
作品提交截止时间是什么？
```

## 5. OCR 与材料审核

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/ocr/parse` | OCR / 文档解析 |
| POST | `/api/audit/upload` | 上传材料并解析 |
| POST | `/api/audit/extract-fields` | 从材料文本中抽取字段 |
| POST | `/api/audit/run` | 运行材料规则审核 |
| POST | `/api/audit` | 兼容审核接口 |

审核输出建议包含：

- 审核结论
- 缺失字段
- 风险提示
- 规则依据
- 修改建议

## 6. 表单与工作流

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/forms/prefill` | 根据抽取字段生成表单草稿 |
| POST | `/api/workflow/plan` | 生成下一步办理待办 |

## 7. Agent 综合办理

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/agent/run` | 串联问答、审核、表单、工作流等模块的综合办理接口 |

当前版本采用模块化轻量编排，包含 Intent、RAG、Audit、Form、Workflow、Record 等能力边界。后续可平滑升级为 LangGraph 状态图。

## 8. 记录留痕

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/history/recent` | 获取最近历史记录 |
| GET | `/api/history/tasks/recent` | 获取最近任务 |
| GET | `/api/history/tasks/{task_id}` | 获取任务详情 |
| POST | `/api/history/records/save` | 保存办理记录 |
| GET | `/api/tasks/recent` | 兼容任务列表接口 |
| GET | `/api/tasks/{task_id}` | 兼容任务详情接口 |
| POST | `/api/records/save` | 兼容记录保存接口 |

## 9. 审阅与规则

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/rules` | 获取规则配置 |
| POST | `/api/review/records` | 创建人工复核记录 |
| PATCH | `/api/review/records/{record_id}` | 更新人工复核记录 |
| GET | `/api/review/records` | 获取人工复核记录 |

## 10. 扩展与导出

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/capabilities` | 获取系统能力说明 |
| GET | `/api/extensions/model/check` | 检查模型接入状态 |
| GET | `/api/extensions/agent-graph` | 获取 Agent 编排说明 |
| GET | `/api/extensions/datasets/faq.jsonl` | 导出 FAQ 样本 |
| GET | `/api/extensions/datasets/ocr-fields.jsonl` | 导出 OCR 字段样本 |
| GET | `/api/extensions/datasets/rules.json` | 导出规则样本 |
| GET | `/api/extensions/local-model-guide` | 获取本地模型接入说明 |
| GET | `/api/extensions/scenario-templates` | 获取场景模板 |
| GET | `/api/exports/audit/latest` | 导出最近审核摘要 |
| GET | `/api/exports/form/latest` | 导出最近表单摘要 |
| GET | `/api/exports/workflow/latest` | 导出最近工作流摘要 |
| GET | `/api/exports/demo/latest` | 导出演示摘要 |


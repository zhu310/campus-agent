# 智审通 Campus Copilot 操作手册

这份文档用于赛前最后准备和现场演示。目标不是继续堆功能，而是把主链路稳定、清楚、有业务价值地展示出来。

## 1. 赛前必须准备的账号和网站

### 1.1 国产模型 API

任选一个稳定可用的平台。不要现场临时申请，至少提前一天测试。

推荐顺序：

1. DeepSeek
   - 网站：https://platform.deepseek.com/
   - 操作：注册登录 -> API keys -> 创建 key
   - `.env` 推荐：
     ```env
     MODEL_PROVIDER=deepseek
     DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
     DEEPSEEK_API_KEY=your-deepseek-key
     DEEPSEEK_LLM_MODEL=deepseek-chat
     EMBEDDING_BASE_URL=http://127.0.0.1:11434/v1
     EMBEDDING_API_KEY=ollama
     EMBEDDING_MODEL=bge-m3
     DEMO_MODE=false
     ```

2. 阿里云百炼
   - 网站：https://bailian.console.aliyun.com/
   - 操作：开通模型服务 -> 获取 API Key -> 选择 Qwen 模型
   - 注意：如果使用其他 OpenAI-compatible 平台，可走 `MODEL_PROVIDER=custom`，并配置 `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`LLM_MODEL`。

3. 火山引擎方舟
   - 网站：https://console.volcengine.com/ark/
   - 操作：开通模型推理 -> 创建 API Key -> 选择国产模型

赛前验收：

```powershell
cd E:\思途杯\campus-agent\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

打开：

```text
http://localhost:8000/api/extensions/model/check
```

确认：

```text
mode = real
api_key_configured = true
base_url 是你配置的平台地址
```

### 1.2 本地国产模型备用方案

如果现场网络不稳，可以准备本地模型备用。

最简单方案：Ollama。

1. 打开：https://ollama.com/download
2. 下载 Windows 版并安装。
3. 安装完成后打开 PowerShell：
   ```powershell
   ollama pull qwen2.5:7b-instruct
   ollama serve
   ```
4. 如果使用 OpenAI-compatible 转接，请确保本地服务暴露 `/v1` 接口。
5. `.env` 示例：
   ```env
   MODEL_PROVIDER=qwen_local
   QWEN_BASE_URL=http://127.0.0.1:11434/v1
   QWEN_API_KEY=ollama
   QWEN_LLM_MODEL=qwen2.5:7b-instruct
   EMBEDDING_BASE_URL=http://127.0.0.1:11434/v1
   EMBEDDING_API_KEY=ollama
   EMBEDDING_MODEL=bge-m3
   DEMO_MODE=false
   ```

说明：Ollama 的 OpenAI 兼容能力依版本而定，赛前必须实际测试。不要第一次在现场试。

### 1.3 Docker 数据库与向量库

你的 PostgreSQL 和 Qdrant 已经在服务器运行。赛前用 XShell 检查：

```bash
docker ps
```

必须看到：

```text
agentic-postgres
qdrant
```

本机 PowerShell 检查端口：

```powershell
Test-NetConnection 103.117.123.28 -Port 5432
Test-NetConnection 103.117.123.28 -Port 6333
```

都必须是：

```text
TcpTestSucceeded : True
```

## 2. 本地启动顺序

### 2.1 XShell

```bash
docker ps
```

如果容器没启动：

```bash
docker start agentic-postgres
docker start qdrant
```

### 2.2 VS Code 后端终端

```powershell
cd E:\思途杯\campus-agent\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

检查：

```text
http://localhost:8000/health
http://localhost:8000/api/extensions/model/check
```

### 2.3 VS Code 前端终端

```powershell
cd E:\思途杯\campus-agent\frontend
npm run dev
```

打开：

```text
http://localhost:5173/
```

浏览器强刷新：

```text
Ctrl + F5
```

## 3. 现场演示文件准备

至少准备 4 个文件，放到桌面文件夹，现场不要到处找。

建议文件夹：

```text
桌面\智审通演示材料\
```

放入：

1. 比赛通知 PDF
   - 用于 RAG 问答。
   - 必须包含：每队 3-5 人、报名截止 5月12日18:00、作品提交截止 5月30日、提交邮箱。

2. 报名表 DOCX
   - 用于字段抽取、审核、表单预填。
   - 确保包含：项目名称、团队成员、电话、邮箱、学院、指导教师。

3. 报名表截图或扫描图片
   - 用于展示 OCR。
   - 字体清晰，截图不要过度压缩。

4. 备用材料文本
   - 放一个 TXT，里面是已经识别好的报名材料文本。
   - 如果 OCR 现场慢或失败，直接粘贴文本继续演示。

## 4. 最稳演示脚本

总时长控制在 4 分钟内。

### 第一步：Dashboard

讲法：

> 这是面向高校行政与学生事务的一站式智能审批与材料办理平台。它不是普通聊天机器人，而是把制度问答、材料审核、表单预填、待办生成和留痕管理串成一个闭环。

点击：进入智能办理。

### 第二步：上传规则/表单模板

左侧文件中心：

1. 上传类型选“规则/模板”。
2. 上传比赛通知 PDF。
3. 勾选该文件。
4. 点击查看，展示可预览内容。

讲法：

> 上传后系统会解析 PDF/DOCX/TXT，切块后写入 Qdrant，问答时只基于选中文件检索。

### 第三步：RAG 问答

问题 1：

```text
单人能否参赛？
```

展示点：

- 结论
- 依据
- 建议动作
- 右侧引用片段

问题 2：

```text
报名截止时间是什么？
```

讲法：

> 这里不是模型自由发挥，回答右侧带有命中文档片段，评委可以直接看到依据。

### 第四步：上传报名材料

左侧上传类型选“个人材料”，上传 DOCX、PDF、图片或粘贴填写草稿。

点击：

```text
提取材料信息
```

必须展示：

- 负责人
- 团队人数
- 联系方式
- 项目名称
- 团队成员
- 学校/学院
- 邮箱

如果 OCR 图片效果不稳，使用 DOCX 或粘贴文本，不要硬等。

### 第五步：审核并补全

点击：

```text
审核并补全
```

讲法：

> 系统会根据当前场景规则检查必填项、人数范围和材料完整性，输出通过、待补充或退回，并继续生成补全追问、可复制草稿和风险建议。

### 第六步：生成表单草稿

点击：

```text
生成表单草稿
```

讲法：

> 表单草稿不是原 Word 版式回填，而是把识别出来的字段映射到上传模板中的真实字段，并展示缺失项和复核提示。

### 第七步：生成办理清单

点击：

```text
生成办理清单
```

展示：

- 步骤清单
- 截止时间
- 风险提醒

### 第八步：记录留痕

点击顶部：

```text
记录留痕
```

展示最近问答、审核、表单、待办记录。

讲法：

> 每次工具调用都会写入数据库，便于老师和学院后续追踪办理过程。

## 5. 拓展中心怎么讲

不要说“我已经完整训练了模型”。正确说法：

> 主链路已稳定落地，拓展中心提供模型接入、Agent 编排、数据集导出和场景扩展能力。

展示顺序：

1. 模型接入
   - 展示 `DEMO_MODE=false`
   - 展示 DeepSeek/Qwen/OpenAI-compatible 地址。
   - 展示 embedding 使用本地 Ollama `bge-m3`。

2. Agent 编排
   - 展示 Intent/RAG/Audit/Form/Workflow/Record 节点。
   - 说明后端已提供 `/api/agent/run` 综合办理接口。

3. 数据集导出
   - 点击导出 FAQ 样本。
   - 点击导出 OCR 字段样本。
   - 点击导出规则样本。

4. 场景扩展
   - 说明除了五个预置场景，还支持其他场景输入，如实践周志、科研立项、宿舍维修。

## 6. 现场故障备用方案

### 6.1 模型 API 失败

现象：

```text
模型不返回 / 请求超时
```

处理：

1. 不要现场调试太久。
2. 说明系统有降级能力。
3. 展示已上传并勾选的通知/规则文件的 RAG 结果和结构化审核。

### 6.2 OCR 慢或识别差

处理：

1. 改用 DOCX 报名表。
2. 或把备用 TXT 内容粘贴到“材料核验与填表”文本框。
3. 继续演示字段抽取、审核、表单和待办。

### 6.3 Qdrant 连接失败

处理：

1. XShell 检查：
   ```bash
   docker ps
   docker start qdrant
   ```
2. PowerShell 检查：
   ```powershell
   Test-NetConnection 103.117.123.28 -Port 6333
   ```

### 6.4 前端页面没有更新

处理：

```text
Ctrl + F5
```

或者关闭 `npm run dev` 后重新启动。

## 7. 评委可能问的问题

### Q1：这和普通 ChatGPT 问答有什么区别？

答：

> 普通聊天只回答问题，本系统是办理闭环：制度上传、RAG 引用问答、材料 OCR/解析、字段抽取、规则审核、表单预填、待办生成和记录留痕。它能做事，不只是聊天。

### Q2：是否支持国产模型？

答：

> 支持。后端采用 OpenAI-compatible 适配方式，可以切换 DeepSeek、Qwen、百炼、火山或本地国产模型服务。拓展中心可以查看当前模型接入状态。

### Q3：是否真的有工具调用？

答：

> 有。后端工具链包括 search_knowledge、ocr_parse_file、extract_fields、validate_rules、prefill_form、generate_todo_plan、save_record，并写入 tool_logs。

### Q4：如果上传的文件既是通知又是材料怎么办？

答：

> 文件中心支持“两者都是”。同一个文件既可以作为规则/模板用于问答，也可以作为个人材料或填写草稿进行抽取和审核。

### Q5：是否支持其他高校事务？

答：

> 支持。五个场景是预置演示入口，工作台还支持自定义场景，复用同一套问答、抽取、审核、表单、待办链路。

## 8. 最终冲奖重点

不要把时间花在解释技术名词上。评委最容易记住三句话：

1. 它不是聊天框，是高校事务办理闭环。
2. 每个回答都有制度依据，每次审核都有缺失项和建议。
3. 同一套链路可以复用到比赛报名、请假、奖助学金、报销、社团活动和其他行政场景。

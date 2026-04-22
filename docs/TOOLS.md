# 工具列表

## 直接返回类（本地执行，无需 AI）

### web_search
- **描述**：Tavily 实时联网搜索
- **参数**：`query` (string) — 搜索关键词
- **返回**：搜索结果文本
- **用途**：查天气、新闻、实时信息

### create_reminder
- **描述**：在 iCloud「小虾待办」创建提醒
- **参数**：`title` (必填)，`note` (可选)
- **返回**：创建结果文本
- **示例**：「帮我记一下明天开会」

### list_reminders
- **描述**：列出 iCloud「小虾待办」所有待办
- **参数**：无
- **返回**：待办列表

### complete_reminder
- **描述**：将匹配的待办标记为已完成
- **参数**：`title` (必填，关键词匹配)
- **返回**：操作结果
- **示例**：「帮我把明天开会标记完成」

### list_calendar_events
- **描述**：查询 iCloud「工作」日历今明两天的日程
- **参数**：无
- **返回**：日程列表（含时间地点）

### create_calendar_event
- **描述**：在 iCloud「工作」日历创建日程
- **参数**：`summary`, `start_datetime`, `end_datetime`, `note` (可选), `location` (可选)
- **返回**：创建结果
- **示例**：「帮我约明天上午10点开会」

---

## 异步返回类

### send_message
- **描述**：向 OpenClaw AI Agent 发送消息
- **参数**：`message` (必填), `name` (说话者名称)
- **返回**：确认文本「🦐 虾小二收到！」
- **结果送达**：通过飞书 Bot 推送
- **用途**：复杂问题、翻译、写作、规划等需要 AI 处理的任务

---

## 实现细节

### iCloud 工具（AppleScript）

iCloud 工具通过 `osascript` 执行 AppleScript：
- **macOS only** — 需要 macOS 系统
- **Reminders**：使用 `make new reminder` / `set completed of`
- **Calendar**：使用 `make new event`

### Tavily 搜索

调用本地 shell 脚本 `tavily_search.sh`，需要提前安装配置好 Tavily API。

### 飞书推送

使用飞书企业自建应用 OAuth API：
1. 获取 tenant_access_token
2. 发送 IM 消息

需要配置环境变量：`FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_TO`

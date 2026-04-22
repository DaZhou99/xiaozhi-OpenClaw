# xiaozhi-openclaw-bridge

🤖 小智语音助手 ↔ OpenClaw AI Agent 桥接工具，通过 MCP 协议连接。

小智设备语音指令 → MCP 工具 → OpenClaw AI Agent → 飞书结果推送。

> 基于 [userplot/xiaozhi-openclaw-bridge](https://github.com/userplot/xiaozhi-openclaw-bridge) 改进，修复了跨平台问题，增加了 iCloud 工具支持。

## 功能特点

- **6 个开箱即用的 MCP 工具**：
  - `web_search` — Tavily 实时联网搜索
  - `create_reminder` / `list_reminders` / `complete_reminder` — iCloud 提醒事项
  - `list_calendar_events` — iCloud 日历
  - `send_message` — OpenClaw AI（结果通过飞书推送）
- **跨平台修复** — Windows / macOS 通用（解决了管道死锁问题）
- **自动重连** — 优雅处理小智服务端 30 秒空闲超时
- **本地执行** — iCloud 工具直接返回结果，无需 AI 往返

### 两种任务，两种路径

**简单任务 → 小智直接语音播报（毫秒级响应）**

> "小智，明天有什么日程？"
> → 直接查 iCloud 日历 → 小智语音回答："明天上午10点有会议"

> "小智，帮我记一下下午三点给客户打电话"
> → 直接创提醒 → 小智语音回答："好的，已记下"

**复杂任务 → OpenClaw AI 处理，结果飞书推送**

> "小智，帮我写一篇关于智能家居行业现状的调研文章"
> → 小智说："好的，正在处理，稍后结果发到飞书"
> → OpenClaw AI 搜索、整合、写稿 → 飞书收到完整文章

> "小智，帮我做一个端午节活动策划方案"
> → 小智说："稍等，马上好"
> → OpenClaw 多工具协同 → 飞书收到完整方案文档

## 架构图

```
┌──────────────────────────────────────────────────────────────┐
│                        小智设备                               │
│                   (MCP Client / 语音助手)                     │
└─────────────────────┬────────────────────────────────────────┘
                      │ WebSocket (MCP 协议)
                      ▼
┌──────────────────────────────────────────────────────────────┐
│                   xiaozhi-openclaw-bridge                    │
│  ┌────────────────────┐    ┌────────────────────────────┐    │
│  │   mcp_pipe.py      │───▶│   openclaw_tool.py         │    │
│  │   (WebSocket ↔ STDIO│    │   (MCP 工具处理器)          │    │
│  │    桥接器)          │    │   • web_search             │    │
│  └────────────────────┘    │   • iCloud 提醒/日历         │    │
│                            │   • send_message           │    │
│                            └──────────┬─────────────────┘    │
└──────────────────────────────────────┼───────────────────────┘
                                       │ HTTP / hook API
                                       ▼
┌──────────────────────────────────────────────────────────────┐
│                        OpenClaw AI Agent                      │
│                   (http://127.0.0.1:18789)                    │
└──────────────────────────────────────────────────────────────┘
                                       │
                                       │ 结果推送
                                       ▼
                          ┌────────────────────┐
                          │   飞书 Bot          │
                          │   （结果消息推送）   │
                          └────────────────────┘
```

## 适用场景

如果你有以下需求，这个桥接方案值得一试：

- 想用**语音助手**控制智能家居、查日历、定提醒，但不想每次都掏手机
- 希望小智能**即问即答**（"明天天气怎样" "帮我记一下开会"），不用等
- 但又有复杂任务需要**强大的 AI 能力**（写文章、做方案、深度调研），希望能用语音触发
- 想把**小智的语音交互**和**OpenClaw 的工具生态**打通

→ 这个桥接让小智同时做到：**简单问题秒答，复杂问题交给 OpenClaw**。

### 1. 环境要求

- Python 3.9+
- [小智服务器](https://github.com/KennoWang/xiaozhi-server)（云端或自建）
- OpenClaw Gateway（本地运行）
- macOS（使用 iCloud 工具需要）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置

```bash
cp config.example.json config.json
# 用文本编辑器打开 config.json，填入你的凭据
```

必须填写的字段：
- `MCP_ENDPOINT` — 小智 MCP WebSocket 地址（从小智服务器控制台获取）
- `HOOK_TOKEN` — OpenClaw hook token
- `OPENCLAW_URL` — OpenClaw Gateway 地址

### 4. 运行

```bash
python mcp_pipe.py openclaw_tool.py
```

### 5. 配置小智 MCP 桥接

在小智服务器管理后台，添加新的 MCP 端点：
```
ws://<你的服务器>:18789/mcp/?token=<你的token>
```
指向运行本桥接服务的地址。

## 工具列表

| 工具 | 说明 | 返回方式 |
|------|------|----------|
| `web_search` | Tavily 联网搜索 | 直接返回 |
| `create_reminder` | 在 iCloud 创建提醒 | 直接返回 |
| `list_reminders` | 查看 iCloud 所有待办 | 直接返回 |
| `complete_reminder` | 将 iCloud 待办标记完成 | 直接返回 |
| `list_calendar_events` | 查看今明两天日历日程 | 直接返回 |
| `send_message` | 发送给 OpenClaw AI 处理 | 通过飞书推送结果 |

## 常见问题

详见 [部署指南](docs/DEPLOY.md)。

## 致谢

- **原项目**：[userplot/xiaozhi-openclaw-bridge](https://github.com/userplot/xiaozhi-openclaw-bridge) — 本项目 fork 自此，增加了跨平台修复和 iCloud 工具
- **小智服务器**：[KennoWang/xiaozhi-server](https://github.com/KennoWang/xiaozhi-server)
- **OpenClaw**：[openclaw/openclaw](https://github.com/openclaw/openclaw)

## 开源协议

MIT License — 详见 [LICENSE](LICENSE)

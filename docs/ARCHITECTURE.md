# 架构设计

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      XiaoZhi 设备                           │
│              (MCP Client / 语音助手)                        │
└────────────────────────┬────────────────────────────────────┘
                         │  WebSocket (MCP Protocol)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   xiaozhi-openclaw-bridge                    │
│                                                              │
│   ┌──────────────────┐    ┌──────────────────────────────┐   │
│   │    mcp_pipe.py   │    │      openclaw_tool.py        │   │
│   │                  │    │                              │   │
│   │  WS Client       │───▶│  MCP Request Handler         │   │
│   │  (小智连接)       │    │                              │   │
│   │                  │    │  • web_search      → Tavily  │   │
│   │  STDIO Bridge    │    │  • iCloud reminders (AppleScript)
│   │  ↔ subprocess    │    │  • iCloud calendar (AppleScript)
│   │                  │    │  • send_message   → OpenClaw  │   │
│   └──────────────────┘    └──────────────────────────────┘   │
│                                                              │
│   重连逻辑: 指数退避 (1s → 2s → 4s → ... → max 300s)          │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP / hook API
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    OpenClaw AI Agent                        │
│                   (本机 127.0.0.1:18789)                    │
└──────────────────────────┬───────────────────────────────────┘
                           │ 飞书推送
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      飞书 Bot                               │
│              (结果消息推送给用户)                             │
└─────────────────────────────────────────────────────────────┘
```

## 核心模块

### mcp_pipe.py — 桥梁核心

职责：
- 维护与小智服务器的 WebSocket 连接（MCP Endpoint）
- 启动 `openclaw_tool.py` 作为子进程
- 在 WebSocket 和 STDIO 之间转发 JSON-RPC 消息

**关键设计决策：**

1. **stderr=DEVNULL** — 防止 FastMCP Banner 填满 pipe buffer 导致死锁
2. **二进制模式 STDIO** — 避免 Windows GBK / macOS UTF-8 编码冲突
3. **BOM 过滤** — Windows PowerShell 可能注入 UTF-8 BOM
4. **自动重连** — 小智服务端 30s 空闲超时，用指数退避重连

### openclaw_tool.py — 工具处理器

职责：
- 实现 6 个 MCP 工具
- 处理 JSON-RPC 请求/响应
- 维护 keepalive ping（每 5 秒发到 stdout）

**工具分类：**

| 类型 | 工具 | 特点 |
|------|------|------|
| 本地执行 | web_search | 调用 Tavily API，直接返回 |
| 本地执行 | iCloud 工具 | AppleScript，直接返回 |
| 异步执行 | send_message | 走 OpenClaw AI，结果发飞书 |

## 通信协议

### 小智 ↔ Bridge (WebSocket)

```
小智 Server  ──JSON-RPC──▶  mcp_pipe.py  ──line-delimited JSON──▶  openclaw_tool.py
                  ◀────────── JSON-RPC响应 ───────────────
```

### Bridge ↔ OpenClaw (HTTP)

```
openclaw_tool.py  ──POST /hooks/agent──▶  OpenClaw Gateway
                   ◀────── 202 Accepted ──────────

OpenClaw  ──处理完成──▶  飞书 Bot  ──结果消息──▶  用户手机
```

## 配置加载优先级

```
环境变量  >  config.json  >  DEFAULT_CONFIG
```

（所有敏感字段支持环境变量覆盖，适合容器化部署）

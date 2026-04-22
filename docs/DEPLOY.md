# 部署指南

## 系统要求

- Python 3.9+
- macOS（iCloud 工具需要 macOS，Linux 仅支持 web_search / send_message）
- [OpenClaw Gateway](https://github.com/openclaw/openclaw) 运行中
- [XiaoZhi Server](https://github.com/KennoWang/xiaozhi-server)（云端或自建）

## 安装

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/xiaozhi-openclaw-bridge.git
cd xiaozhi-openclaw-bridge

# 安装依赖
pip install -r requirements.txt
```

## 配置

```bash
cp config.example.json config.json
# 编辑 config.json，填入你的凭据
```

### 必须配置

| 字段 | 说明 | 获取方式 |
|------|------|----------|
| `MCP_ENDPOINT` | XiaoZhi MCP WebSocket URL | xiaozhi-server 控制台 |
| `HOOK_TOKEN` | OpenClaw hook token | OpenClaw 控制台 |
| `OPENCLAW_URL` | OpenClaw Gateway 地址 | 默认 `http://127.0.0.1:18789` |

### 可选配置

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `FEISHU_APP_ID` | 空 | 飞书应用 App ID |
| `FEISHU_APP_SECRET` | 空 | 飞书应用 App Secret |
| `FEISHU_TO` | 空 | 飞书推送目标用户 open_id |
| `REMINDER_LIST` | "Reminders" | iCloud 提醒列表名称 |
| `CALENDAR_NAME` | "Calendar" | iCloud 日历名称 |
| `SESSION_KEY` | 空 | OpenClaw session key |

### 环境变量覆盖

所有配置均支持环境变量覆盖：

```bash
export MCP_ENDPOINT="wss://api.xiaozhi.me/mcp/?token=YOUR_TOKEN"
export HOOK_TOKEN="YOUR_HOOK_TOKEN"
export OPENCLAW_URL="http://127.0.0.1:18789"
```

## 运行

```bash
# 直接运行
python mcp_pipe.py openclaw_tool.py

# 查看日志
python mcp_pipe.py openclaw_tool.py >> bridge.log 2>&1 &

# 查看状态
ps aux | grep mcp_pipe | grep -v grep
tail -f bridge.log
```

## 常见问题

### 1. 连接建立后 30 秒断连

**原因**：小智服务端有 30 秒空闲超时。

**解决**：Bridge 内置自动重连机制（指数退避 1s → 2s → ... → max 300s），断连后 1-2 秒自动恢复，用户无感知。

### 2. 管道死锁 / 子进程无响应

**原因**：FastMCP 启动时向 stderr 打印 Banner，填满 pipe buffer 后阻塞。

**解决**：已在代码中修复（`stderr=DEVNULL`），使用最新版本即可。

### 3. macOS 上 iCloud 工具报错

**原因**：AppleScript 执行权限未开启。

**解决**：系统设置 → 隐私与安全性 → 自动化 → 允许「终端」访问「提醒事项」和「日历」。

### 4. 飞书推送失败

**检查**：
1. `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 是否正确
2. 飞书应用是否有「发消息」权限
3. `FEISHU_TO` 是否是正确的 open_id

### 5. web_search 无结果

**检查**：确认 `tavily_search.sh` 脚本路径正确，且 Tavily API key 有效。

## macOS 自动启动（launchd）

```bash
# 复制 plist 模板
cp scripts/com.dz.xiaozhi-openclaw-bridge.plist ~/Library/LaunchAgents/

# 编辑 plist，修改路径
nano ~/Library/LaunchAgents/com.dz.xiaozhi-openclaw-bridge.plist

# 加载
launchctl load ~/Library/LaunchAgents/com.dz.xiaozhi-openclaw-bridge.plist
```

## 重启 Bridge

```bash
pkill -f "mcp_pipe.py"; sleep 2
cd /path/to/xiaozhi-openclaw-bridge
python mcp_pipe.py openclaw_tool.py >> bridge.log 2>&1 &
```

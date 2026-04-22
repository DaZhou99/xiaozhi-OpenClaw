#!/usr/bin/env python3
"""
openclaw_tool.py — MCP tool handler for xiaozhi-openclaw-bridge

Provides 6 tools:
- web_search: Tavily real-time search
- create_reminder / list_reminders / complete_reminder: iCloud Reminders
- list_calendar_events: iCloud Calendar
- send_message: OpenClaw AI Agent (results via Feishu)

All sensitive config is read from config.json / environment variables.
"""

import json
import os
import subprocess
import sys
import threading
import time
import requests

# ---- Config helpers ----
def _get_config():
    try:
        from config import load_config
        return load_config()
    except Exception:
        return {}


def _cfg(key, default=""):
    return _get_config().get(key, default)


# ---- iCloud tool settings (customizable) ----
REMINDER_LIST = os.environ.get("REMINDER_LIST", "Reminders")
CALENDAR_NAME = os.environ.get("CALENDAR_NAME", "Calendar")

# ---- Feishu (飞书) settings ----
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_TO = os.environ.get("FEISHU_TO", "")


# ---- Tool implementations ----

def compact(d):
    """Remove None/empty values from dict."""
    return {k: v for k, v in d.items() if v not in (None, "", [])}


def run_applescript(script, timeout=10):
    """Execute AppleScript, return (stdout, success)."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.returncode == 0
    except subprocess.TimeoutExpired:
        return "⏱️ 执行超时，请稍后重试", False
    except Exception as e:
        return f"❌ 执行错误：{e}", False


def get_feishu_token():
    """Get Feishu tenant access token."""
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        return ""
    try:
        r = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
            timeout=5
        )
        return r.json().get("tenant_access_token", "")
    except Exception:
        return ""


def send_feishu(token, text):
    """Send text message via Feishu bot."""
    if not token or not FEISHU_TO:
        return
    try:
        requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "receive_id": FEISHU_TO,
                "msg_type": "text",
                "content": json.dumps({"text": text})
            },
            timeout=10
        )
    except Exception as e:
        print(f"[Feishu Error] {e}", flush=True)


def call_tavily(query):
    """Run Tavily search via shell script."""
    script_path = os.environ.get("TAVILY_SCRIPT", "tavily_search.sh")
    r = subprocess.run(
        ["bash", script_path, query],
        capture_output=True, text=True, timeout=10
    )
    return r.stdout.strip() or "搜索无结果"


def create_reminder(title, note=""):
    """Create a reminder in iCloud Reminders."""
    # Ensure list exists
    check_script = f'tell application "Reminders" to get name of lists'
    lists_output, ok = run_applescript(check_script, timeout=5)
    if not ok:
        return f"获取列表失败：{lists_output}"

    if REMINDER_LIST not in lists_output:
        create_list_script = f'tell application "Reminders" to make new list with properties {{name:"{REMINDER_LIST}"}}'
        out, ok = run_applescript(create_list_script, timeout=5)
        if not ok:
            return f"创建「{REMINDER_LIST}」列表失败：{out}"

    safe_title = title.replace('"', '\\"').replace("\n", " ")
    safe_note = note.replace('"', '\\"').replace("\n", " ") if note else ""

    if safe_note:
        script = f'tell application "Reminders" to make new reminder at end of reminders of list "{REMINDER_LIST}" with properties {{name:"{safe_title}", body:"{safe_note}"}}'
    else:
        script = f'tell application "Reminders" to make new reminder at end of reminders of list "{REMINDER_LIST}" with properties {{name:"{safe_title}"}}'

    out, ok = run_applescript(script, timeout=5)
    if ok:
        return f"✅ 已记下：{title}"
    else:
        return f"❌ 创建失败：{out}"


def complete_reminder(title):
    """Mark a reminder as completed."""
    safe_title = title.replace('"', '\\"')
    script = f'tell application "Reminders" to set completed of (first reminder of list "{REMINDER_LIST}" whose name contains "{safe_title}") to true'
    out, ok = run_applescript(script, timeout=5)
    if ok:
        return f"✅ 已完成：{title}"
    else:
        return f"❌ 操作失败：{out}"


def list_reminders():
    """List all reminders in the configured iCloud list."""
    script = f'tell application "Reminders" to get name of reminders of list "{REMINDER_LIST}"'
    out, ok = run_applescript(script, timeout=8)
    if not ok:
        if "not found" in out.lower() or "错误" in out:
            return f"📋 「{REMINDER_LIST}」里没有待办"
        return f"❌ 查询失败：{out}"
    if not out.strip() or out.strip() == "missing value":
        return f"📋 「{REMINDER_LIST}」里没有待办"
    lines = [l.strip() for l in out.strip().split(",") if l.strip() and l.strip() != "missing value"]
    if not lines:
        return f"📋 「{REMINDER_LIST}」里没有待办"
    header = f"📋 **{REMINDER_LIST}**（共 {len(lines)} 项）：\n"
    return header + "\n".join([f"{i}. {l}" for i, l in enumerate(lines, 1)])


def list_calendar_events():
    """List today's and tomorrow's events from the configured iCloud calendar."""
    script = f'''
tell application "Calendar"
    set today to current date
    set tomorrow to today + 86400
    set dayAfter to today + 86400 * 2
    set evts to events of calendar "{CALENDAR_NAME}" whose start date >= today and start date < dayAfter
    set output to ""
    repeat with e in evts
        set output to output & summary of e & "|" & start date of e as text & "|"
    end repeat
    if output is "" then set output to "EMPTY"
    return output
end tell
'''
    out, ok = run_applescript(script, timeout=10)
    if not ok:
        return f"❌ 查询失败：{out}"
    if out.strip() == "EMPTY":
        return f"📅 「{CALENDAR_NAME}」今天和明天没有日程"
    items = [i.strip() for i in out.strip().split("|") if i.strip()]
    lines = []
    for i in range(0, len(items), 3):
        if i+2 < len(items):
            lines.append(f"• {items[i]} @ {items[i+1]}")
    if not lines:
        return f"📅 「{CALENDAR_NAME}」今天和明天没有日程"
    header = f"📅 **「{CALENDAR_NAME}」今明两天日程**（共 {len(lines)} 项）：\n"
    return header + "\n".join(lines)


def create_calendar_event(summary, start_datetime, end_datetime, note="", location=""):
    """Create a calendar event in iCloud."""
    safe_summary = summary.replace('"', '\\"')
    safe_note = note.replace('"', '\\"') if note else ""
    safe_location = location.replace('"', '\\"') if location else ""

    def parse_time(ts):
        ts = ts.strip()
        if "T" in ts:
            date_part, time_part = ts.split("T")
            time_part = time_part[:5] if ":" in time_part else time_part
        else:
            date_part, time_part = ts.split(" ")
        return f"{date_part} {time_part}"

    start_str = parse_time(start_datetime)
    end_str = parse_time(end_datetime)

    props = f'summary:"{safe_summary}", start date:date "{start_str}", end date:date "{end_str}"'
    if safe_note:
        props += f', description:"{safe_note}"'
    if safe_location:
        props += f', location:"{safe_location}"'

    script = f'''
tell application "Calendar"
    tell calendar "{CALENDAR_NAME}"
        make new event at end with properties {{{props}}}
    end tell
    return "OK"
end tell
'''
    out, ok = run_applescript(script, timeout=10)
    if ok:
        return f"✅ 日程已创建：\n📅 {summary}\n🕐 {start_str} → {end_str}"
    else:
        return f"❌ 创建失败：{out}"


def bg_openclaw(message, session_key, speaker=""):
    """Call OpenClaw hook API asynchronously, send result to Feishu."""
    payload = compact({
        "message": message,
        "name": _cfg("HOOK_NAME"),
        "deliver": True,
        "wakeMode": _cfg("WAKE_MODE", "now"),
        "agentId": _cfg("AGENT_ID"),
        "channel": _cfg("CHANNEL", "feishu"),
        "sessionKey": session_key,
        "to": FEISHU_TO,
        "model": _cfg("MODEL"),
        "timeoutSeconds": int(_cfg("TIMEOUT_SECONDS", 120)),
    })
    hook_token = _cfg("HOOK_TOKEN", "")
    try:
        resp = requests.post(
            f"{_cfg('OPENCLAW_URL', 'http://127.0.0.1:18789')}/hooks/agent",
            headers={"Authorization": f"Bearer {hook_token}", "Content-Type": "application/json"},
            json=payload, timeout=130
        )
        body = resp.json() if resp.ok else {"error": resp.text}
        accepted = resp.status_code in (200, 202)
    except Exception as e:
        body = {"error": str(e)}
        accepted = False

    ft = get_feishu_token()
    if not ft:
        return
    if not accepted:
        send_feishu(ft, f"处理失败：{body.get('error', body)}")


# ---- MCP Tool Definitions ----
TOOLS = [
    {
        "name": "web_search",
        "description": "联网搜索工具，用于查询实时信息、新闻、天气等。直接返回搜索结果。",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "搜索关键词"}},
            "required": ["query"],
        },
    },
    {
        "name": "create_reminder",
        "description": "在 iCloud 创建提醒事项。例如：帮我记一下明天开会。直接返回结果。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "待办标题"},
                "note": {"type": "string", "description": "备注（可选）"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "complete_reminder",
        "description": "将 iCloud 待办标记为已完成。例如：帮我把明天开会标记完成。",
        "inputSchema": {
            "type": "object",
            "properties": {"title": {"type": "string", "description": "待办标题（包含关键词即可）"}},
            "required": ["title"],
        },
    },
    {
        "name": "list_reminders",
        "description": "查询 iCloud 所有待办事项。直接返回列表。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_calendar_events",
        "description": "查询 iCloud 日历今天和明天的所有日程。直接返回结果。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "create_calendar_event",
        "description": "在 iCloud 日历创建日程。例如：帮我约明天上午10点开会。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "日程标题"},
                "start_datetime": {"type": "string", "description": "开始时间，如 '2026-04-22 10:00'"},
                "end_datetime": {"type": "string", "description": "结束时间，如 '2026-04-22 11:00'"},
                "note": {"type": "string", "description": "备注（可选）"},
                "location": {"type": "string", "description": "地点（可选）"},
            },
            "required": ["summary", "start_datetime", "end_datetime"],
        },
    },
    {
        "name": "send_message",
        "description": "向 AI Agent 发送消息，由 AI 处理。结果通过飞书发送。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "name": {"type": "string"},
            },
        },
    },
]

PROTOCOL_VERSION = "2024-11-05"


def keepalive_sender():
    """Send ping notifications every 5 seconds to keep the connection alive."""
    while True:
        time.sleep(5)
        try:
            msg = json.dumps({"jsonrpc": "2.0", "method": "notifications/ping", "params": {}}, ensure_ascii=False)
            sys.stdout.write(msg + "\n")
            sys.stdout.flush()
        except Exception:
            break


def handle(req):
    """Handle an incoming MCP JSON-RPC request."""
    method = req.get("method", "")
    req_id = req.get("id")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": {"name": "xiaozhi-openclaw-bridge", "version": "1.2.0"},
                "capabilities": {"tools": {}},
                "instructions": "xiaozhi-openclaw-bridge with iCloud tools"
            }
        }

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments", {})

        if name == "web_search":
            return {"jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": call_tavily(args.get("query", ""))}]}}

        if name == "create_reminder":
            return {"jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": create_reminder(args.get("title", ""), args.get("note", ""))}]}}

        if name == "complete_reminder":
            return {"jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": complete_reminder(args.get("title", ""))}]}}

        if name == "list_reminders":
            return {"jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": list_reminders()}]}}

        if name == "list_calendar_events":
            return {"jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": list_calendar_events()}]}}

        if name == "create_calendar_event":
            return {"jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": create_calendar_event(
                        args.get("summary", ""), args.get("start_datetime", ""),
                        args.get("end_datetime", ""), args.get("note", ""), args.get("location", "")
                    )}]}}

        if name == "send_message":
            msg = args.get("message", "")
            speaker = args.get("name", "")
            tool_msg = f"[{speaker}] {msg}" if speaker else msg
            ft = get_feishu_token()
            if ft:
                src = speaker if speaker else "小智"
                send_feishu(ft, f"🦐 收到「{src}」指令：{msg}")
            threading.Thread(
                target=bg_openclaw,
                args=(tool_msg, _cfg("SESSION_KEY", ""), speaker)
            ).start()
            return {"jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": "🦐 虾小二收到！正在处理中，结果将通过飞书发送给您，请稍候~"}]}}

        return {"jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"unknown tool: {name}"}}

    if method and not method.endswith("/notification"):
        return {"jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"unknown method: {method}"}}

    return None


# ---- Main loop ----
print("[READY] openclaw_tool", flush=True)

t = threading.Thread(target=keepalive_sender, daemon=True)
t.start()

while True:
    line = sys.stdin.readline()
    if not line:
        break
    try:
        req = json.loads(line.strip())
        resp = handle(req)
        if resp is not None:
            print(json.dumps(resp), flush=True)
    except Exception as e:
        print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}}), flush=True)

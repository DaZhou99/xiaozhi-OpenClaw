# Changelog

## v1.2.0 (2026-04-22)

### Features
- Feishu notification: show "收到指令" confirmation before AI processing
- Remove duplicate runId receipt message

### Bug Fixes
- asyncio + threading conflict: `asyncio.to_thread()` conflicts with daemon keepalive thread
  → Fixed by using pure threading + blocking I/O for subprocess, asyncio only for WebSocket

## v1.1.0 (2026-04-21)

### Features
- Added 4 iCloud tools:
  - `create_reminder` — iCloud Reminders creation
  - `list_reminders` — iCloud Reminders listing (optimized with `get name of reminders`)
  - `complete_reminder` — mark reminder as done (uses `set completed`, not delete)
  - `list_calendar_events` — iCloud Calendar query (today + tomorrow)

### Bug Fixes
- Reminders AppleScript `repeat` loop is slow → use `get name of reminders` for direct access
- Mark-done uses `set completed of ... to true` instead of `delete` (safety first)

## v1.0.0 (2026-04-21)

### Features
- Initial release
- 2 tools: `web_search` (Tavily), `send_message` (OpenClaw AI)
- Core fixes from original project:
  - Pipe buffer deadlock resolved (`stderr=DEVNULL`)
  - UTF-8 BOM stripping
  - Auto-reconnect with exponential backoff
  - Binary mode STDIO for cross-platform compatibility

"""
xiaozhi-openclaw-bridge MCP 管道 — 跨平台优化版

核心修复（Windows + macOS 通用）：
1. 管道死锁：FastMCP 启动时向 stderr 打印大量 Banner，填满 pipe buffer 后
   subprocess.stderr.write() 阻塞，导致子进程无法读取 stdin，小智 30s 超时断连。
   → 解决：stderr=subprocess.DEVNULL，丢弃 Banner

2. UTF-8 解码失败：原始代码用 text 模式（encoding="utf-8"），遇到非 UTF-8 字节直接崩溃。
   → 解决：二进制模式 + errors="replace" 容错

3. UTF-8 BOM 干扰：Windows PowerShell/cmd 可能向数据流注入 BOM（\xef\xbb\xbf），
   导致 JSON-RPC 解析失败。macOS 一般不会，但加上无副作用。
   → 解决：转发前主动 strip BOM

4. 强制 UTF-8 编码：Windows 默认编码是 GBK，不是 UTF-8，会导致中文乱码。
   macOS 默认 UTF-8 不受影响，但统一设置无副作用。
   → 解决：PYTHONIOENCODING=utf-8 环境变量
"""

import sys
from pathlib import Path

# Ensure src/ is on the path so config/bridge_logging can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent))

import asyncio
import json
import logging
import os
import signal
import subprocess
from collections.abc import Sequence
from typing import Union

import websockets
from dotenv import load_dotenv

from bridge_logging import log_event, log_json_message


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mcp_pipe")

INITIAL_BACKOFF_SECONDS = 1
MAX_BACKOFF_SECONDS = 300

# UTF-8 BOM 字节序列（Windows PowerShell/cmd 可能注入，macOS 统一处理）
BOM = b"\xef\xbb\xbf"


def _strip_bom(data: bytes) -> bytes:
    """剥离 UTF-8 BOM，防止 JSON-RPC 解析失败。"""
    if data.startswith(BOM):
        return data[3:]
    return data


async def pipe_websocket_to_process(websocket, process: subprocess.Popen) -> None:
    """从小智 websocket 读取消息，转发到子进程 stdin（二进制模式）。"""
    try:
        while True:
            message = await websocket.recv()
            if isinstance(message, str):
                data = message.encode("utf-8")
            else:
                data = message

            # [修复] strip BOM — Windows 下 PowerShell/cmd 可能注入
            data = _strip_bom(data)

            log_json_message("xiaozhi_to_tool", data.decode("utf-8", errors="replace"))
            process.stdin.write(data + b"\n")
            process.stdin.flush()
    except Exception as exc:
        logger.warning("pipe_websocket_to_process error: %s", exc)
    finally:
        if process.stdin and not process.stdin.closed:
            try:
                process.stdin.close()
            except Exception:
                pass


async def pipe_process_to_websocket(process: subprocess.Popen, websocket) -> None:
    """从子进程 stdout 读取响应（二进制模式），转发到小智 websocket。"""
    while True:
        data = await asyncio.to_thread(process.stdout.readline)
        if not data:
            logger.info("server stdout closed")
            return

        # [修复] strip BOM
        data = _strip_bom(data)

        try:
            log_json_message("tool_to_xiaozhi", data.decode("utf-8", errors="replace"))
        except Exception as e:
            logger.warning("failed to decode server stdout: %s", e)

        try:
            await websocket.send(data)
        except Exception as exc:
            logger.warning("websocket send error: %s", exc)
            return


async def run_once(endpoint_url: str, command: Sequence[str]) -> None:
    process = None
    try:
        logger.info("connecting to MCP endpoint")
        log_event("bridge_connecting", endpoint="configured")

        # [修复] ping_interval=5 每5秒发 WebSocket ping，xiaozhi 服务端如果支持就会响应
        async with websockets.connect(endpoint_url, ping_interval=5, ping_timeout=3) as websocket:
            logger.info("connected to MCP endpoint")

            # [修复] 强制 UTF-8 编码
            # Windows 默认 GBK，中文 JSON-RPC 消息会乱码/解析失败
            # macOS 默认 UTF-8，加上也无副作用
            env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

            process = subprocess.Popen(
                list(command),
                stdin=subprocess.PIPE,     # 二进制模式，手动控制编解码
                stdout=subprocess.PIPE,    # 二进制模式
                # [核心修复] 丢弃 stderr，防止 FastMCP Banner 填满 pipe buffer 导致死锁
                #
                # 死锁原理：
                #   FastMCP 启动 → 打印几百行 Banner 到 stderr
                #   → stderr pipe buffer 满（Windows 4KB，macOS 64KB）
                #   → subprocess.stderr.write() 阻塞
                #   → 子进程卡住，无法读 stdin
                #   → 小智发 initialize 请求但无人响应
                #   → 30s 超时 → 4004 断连
                #
                # macOS 的 64KB buffer 有时够用有时不够，导致偶发断连更难定位。
                # 统一用 DEVNULL 彻底避免此问题。
                stderr=subprocess.DEVNULL,
                env=env,
            )
            logger.info("started tool process: %s", " ".join(command))
            log_event(
                "bridge_connected",
                tool_command=list(command),
                tool_pid=process.pid,
            )
            # 注意：keepalive 现在由工具进程通过 stdout 写 notification 来维护
            await asyncio.gather(
                pipe_websocket_to_process(websocket, process),
                pipe_process_to_websocket(process, websocket),
            )
    except Exception as exc:
        logger.warning("run_once exception: %s", exc)
    finally:
        if process is not None:
            logger.info("stopping tool process")
            log_event("tool_process_stopping", tool_pid=process.pid)
            process.terminate()
            try:
                await asyncio.to_thread(process.wait, 5)
            except subprocess.TimeoutExpired:
                process.kill()


async def run_forever(endpoint_url: str, command: Sequence[str]) -> None:
    attempt = 0
    backoff = INITIAL_BACKOFF_SECONDS
    while True:
        try:
            if attempt > 0:
                logger.info("retrying in %s seconds", backoff)
                await asyncio.sleep(backoff)
            await run_once(endpoint_url, command)
            attempt = 0
            backoff = INITIAL_BACKOFF_SECONDS
        except Exception as exc:  # pragma: no cover
            attempt += 1
            logger.warning("bridge disconnected (attempt %s): %s", attempt, exc)
            log_event("bridge_disconnected", attempt=attempt, error=str(exc))
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)


def install_signal_handlers() -> None:
    """注册 SIGINT/SIGTERM 信号处理，优雅退出。"""
    def _handle_signal(signum, frame):
        logger.info("received signal %s, exiting", signum)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)


def main(argv: Union[Sequence[str], None] = None) -> int:
    from config import load_config, validate_config

    install_signal_handlers()
    args = list(argv or sys.argv[1:])
    tool_script = args[0] if args else "openclaw_tool.py"
    config = load_config()
    errors = validate_config(config)
    if errors:
        for error in errors:
            logger.error(error)
        return 1

    command = [sys.executable, tool_script]
    asyncio.run(run_forever(config["MCP_ENDPOINT"], command))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

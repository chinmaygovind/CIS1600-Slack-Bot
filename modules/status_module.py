"""Replies to any DM sent to the bot with a liveness + stats summary.

Uses Slack Socket Mode, so the bot holds an outbound WebSocket to Slack and
needs no public URL, no inbound port, and no nginx changes on the host.

Requires, in addition to the usual SLACK_API_TOKEN:
  SLACK_APP_TOKEN  -- an app-level token (xapp-...) with connections:write
and on the Slack app: Socket Mode enabled, the `message.im` event subscribed,
and the `im:history` bot scope.
"""

import os
import time
import subprocess
from datetime import datetime
from threading import Event

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

from utils import get_logger

load_dotenv()

BOT_TOKEN = os.getenv("SLACK_API_TOKEN")
APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SERVICES = ["cis1600-ed", "cis1600-birthday", "cis1600-reminder", "cis1600-status"]

logger = get_logger("status_module")
STARTED_AT = time.time()


def human_duration(seconds):
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def host_uptime():
    try:
        with open("/proc/uptime") as f:
            return human_duration(float(f.read().split()[0]))
    except Exception:
        return "unknown"


def memory_line():
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, value = line.partition(":")
                info[key] = int(value.split()[0])  # kB
        total = info["MemTotal"] / 1024
        available = info["MemAvailable"] / 1024
        used = total - available
        return f"{used:.0f} MB used / {total:.0f} MB ({available:.0f} MB free)"
    except Exception:
        return "unknown"


def service_states():
    """(name, active?, uptime) for each bot unit. Read-only; needs no sudo."""
    rows = []
    for svc in SERVICES:
        try:
            active = subprocess.run(
                ["systemctl", "is-active", svc],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            since = subprocess.run(
                ["systemctl", "show", svc, "-p", "ActiveEnterTimestampMonotonic", "--value"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            uptime = ""
            if active == "active" and since.isdigit() and int(since) > 0:
                with open("/proc/uptime") as f:
                    now_monotonic = float(f.read().split()[0])
                uptime = human_duration(now_monotonic - int(since) / 1_000_000)
            rows.append((svc, active, uptime))
        except Exception as e:
            logger.error(f"Could not read state of {svc}: {e}")
            rows.append((svc, "unknown", ""))
    return rows


def build_status():
    lines = [
        f"Hi, I'm alive! Here's my uptime: *{human_duration(time.time() - STARTED_AT)}*",
        "",
        f"*Host:* up {host_uptime()}  |  *Memory:* {memory_line()}",
        f"*Time:* {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
        "*Modules*",
    ]
    for svc, active, uptime in service_states():
        icon = ":large_green_circle:" if active == "active" else ":red_circle:"
        suffix = f" (up {uptime})" if uptime else ""
        lines.append(f"{icon} `{svc}` - {active}{suffix}")

    lines += [
        "",
        f"*Ed course:* {os.getenv('ED_COURSE_ID')} -> #{os.getenv('SLACK_CHANNEL')} "
        f"every {os.getenv('REFRESH_INTERVAL_SECONDS')}s",
    ]
    return "\n".join(lines)


def handle_request(client: SocketModeClient, req: SocketModeRequest):
    # Ack first -- Slack retries anything not acknowledged within 3 seconds.
    if req.type != "events_api":
        return
    client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))

    event = req.payload.get("event", {})
    if event.get("type") != "message" or event.get("channel_type") != "im":
        return
    # Ignore our own messages, other bots, and edits/joins/etc, or we loop.
    if event.get("bot_id") or event.get("subtype"):
        return

    channel = event.get("channel")
    logger.info(f"DM from {event.get('user')} in {channel}; replying with status")
    try:
        client.web_client.chat_postMessage(channel=channel, text=build_status())
    except Exception as e:
        logger.error(f"Failed to reply to DM: {e}")


def main():
    if not APP_TOKEN:
        logger.error("SLACK_APP_TOKEN is not set; Socket Mode cannot start.")
        raise SystemExit(1)

    client = SocketModeClient(app_token=APP_TOKEN, web_client=WebClient(token=BOT_TOKEN))
    client.socket_mode_request_listeners.append(handle_request)
    client.connect()
    logger.info("status_module connected to Slack Socket Mode; waiting for DMs.")
    Event().wait()


if __name__ == "__main__":
    main()

"""Mirror new Ed posts into Slack, with homework context attached in-thread.

For every new Ed post the bot posts a notification as before. When the post can
be tied to a specific homework problem, it then replies in that message's thread
with the problem as it appears in the homework PDF, followed by its solution.

Homework PDFs come from the course Overleaf project over git; see hw_pdfs.py.
Matching is regex over the post plus Ed's own category; see hw_match.py.

The attachment step is fully isolated: any failure in the Overleaf sync, the
LaTeX build, or the upload is logged and DM'd to ADMINS, but never prevents the
Ed notification itself from going out.
"""

import asyncio
import os
import re
import sys
import time

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hw_match
import hw_pdfs
from ed_client import EdClient, EdError
from utils import SlackHelper, get_logger

load_dotenv()

SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "ed-notifications")
REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL_SECONDS", "10"))
HW_SYNC_HOURS = float(os.getenv("HW_SYNC_INTERVAL_HOURS", "12"))
ATTACH_ENABLED = os.getenv("HW_ATTACH_ENABLED", "true").lower() != "false"

logger = get_logger("ed_module")

# Don't re-alert the admins about the same failure every cycle.
ALERT_COOLDOWN_SECONDS = 3600
_last_alert = {}
# Ed/Cloudflare throws brief 502s; only alert once polling has failed this long.
ED_OUTAGE_ALERT_SECONDS = int(os.getenv("ED_OUTAGE_ALERT_SECONDS", "600"))


def alert_admins(slack, key, message):
    now = time.time()
    if now - _last_alert.get(key, 0) < ALERT_COOLDOWN_SECONDS:
        return
    _last_alert[key] = now
    logger.error(message)
    slack.dm_admins(f":warning: *CIS 1600 bot -- {key}*\n{message}")


def ed_html_to_slack(text):
    """Flatten Ed's XML-ish post body into Slack mrkdwn."""
    text = re.sub(r"</?paragraph>", "\n", text or "")
    text = re.sub(r"<(/)?(bold|strong)>", "*", text)
    text = re.sub(r"<(/)?(italic|em)>", "_", text)
    text = re.sub(r"</?code>", "`", text)
    text = re.sub(r"</?pre>", "```", text)
    text = re.sub(r"</?document[^>]*>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def truncate(text, limit=1200):
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def attach_homework(slack, channel_id, thread_ts, thread):
    """Reply in-thread with the referenced problem and its solution."""
    homework, problem, part = hw_match.match(
        thread.get("title", ""),
        thread.get("document") or thread.get("content") or "",
        thread.get("subcategory"),
    )
    if not homework or not problem:
        logger.info(
            f"No homework problem identified for thread #{thread.get('number')} "
            f"(homework={homework}, problem={problem})"
        )
        return

    label = f"{homework} Q{problem}{part or ''}"
    questions, solutions, note = hw_pdfs.problem_attachments(homework, problem)

    if not questions and not solutions:
        logger.info(f"Nothing to attach for {label}: {note}")
        return

    slack.upload_images(
        channel_id, questions, thread_ts=thread_ts,
        comment=f":page_facing_up: *Homework {label} -- problem*",
    )
    if solutions:
        slack.upload_images(
            channel_id, solutions, thread_ts=thread_ts,
            comment=f":white_check_mark: *Homework {label} -- solution*",
        )
    elif note:
        slack.send_message(channel_id, f"_{note}_", thread_ts=thread_ts)
    logger.info(
        f"Attached {label} to thread #{thread.get('number')}: "
        f"{len(questions)} problem page(s), {len(solutions)} solution page(s)"
    )


def announce(slack, channel_id, ed, thread):
    body = ed_html_to_slack(thread.get("document") or thread.get("content") or "")
    message = (
        f"*New Ed Post (#{thread['number']}): {thread.get('title', '')}*\n"
        f"{truncate(body)}\n"
        f"Link: {ed.thread_url(thread['id'])}"
    )
    return slack.send_message(channel_id, message)


async def homework_sync_loop(slack):
    """Pull the Overleaf project and rebuild changed homeworks, every 12h."""
    while True:
        try:
            built, errors = await asyncio.to_thread(hw_pdfs.sync_and_build)
            if built:
                logger.info(f"Rebuilt homeworks: {', '.join(built)}")
            if errors:
                alert_admins(
                    slack, "homework build",
                    "Some homeworks failed to build:\n" + "\n".join(errors[:10]),
                )
        except Exception as e:
            alert_admins(slack, "Overleaf sync", f"Could not sync homework PDFs: {e}")
        await asyncio.sleep(HW_SYNC_HOURS * 3600)


async def poll_ed(slack, channel_id, ed):
    threads = await asyncio.to_thread(ed.list_threads, 50, 0, "new")
    if not threads:
        return
    last_seen = max(t["number"] for t in threads)
    logger.info(f"Watching Ed from post #{last_seen}")
    slack.send_message(channel_id, "EdModule initialized!")

    failing_since = None
    while True:
        try:
            threads = await asyncio.to_thread(ed.list_threads, 50, 0, "new")
            fresh = sorted(
                (t for t in threads if t["number"] > last_seen),
                key=lambda t: t["number"],
            )
            for summary in fresh:
                # The list endpoint truncates bodies; fetch the full post.
                try:
                    thread = await asyncio.to_thread(ed.get_thread, summary["id"])
                except EdError:
                    thread = summary
                thread.setdefault("number", summary["number"])
                thread.setdefault("id", summary["id"])
                thread.setdefault("subcategory", summary.get("subcategory"))

                thread_ts = announce(slack, channel_id, ed, thread)
                last_seen = max(last_seen, thread["number"])

                if ATTACH_ENABLED and thread_ts:
                    try:
                        await asyncio.to_thread(
                            attach_homework, slack, channel_id, thread_ts, thread
                        )
                    except Exception as e:
                        alert_admins(
                            slack, "homework attachment",
                            f"Could not attach homework for Ed post "
                            f"#{thread['number']}: {e}",
                        )
            failing_since = None
        except EdError as e:
            failing_since = failing_since or time.time()
            down_for = time.time() - failing_since
            if down_for >= ED_OUTAGE_ALERT_SECONDS:
                alert_admins(
                    slack, "Ed API",
                    f"{e} (failing for {int(down_for // 60)} min)",
                )
            else:
                logger.warning(f"Ed poll failed, will retry: {e}")
        except Exception as e:
            logger.error(f"Error in EdModule: {e}")
        await asyncio.sleep(REFRESH_INTERVAL)


async def main():
    slack = SlackHelper("ed_module")
    ed = EdClient()
    channel_id = slack.find_channel(SLACK_CHANNEL)
    if not channel_id:
        logger.error(f"Channel #{SLACK_CHANNEL} not found; is the bot invited?")
        raise SystemExit(1)

    try:
        logger.info(f"Ed API authenticated as {ed.whoami()}")
    except EdError as e:
        alert_admins(slack, "Ed API", f"Could not authenticate with Ed: {e}")
        raise SystemExit(1)

    tasks = [poll_ed(slack, channel_id, ed)]
    if ATTACH_ENABLED:
        tasks.append(homework_sync_loop(slack))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())

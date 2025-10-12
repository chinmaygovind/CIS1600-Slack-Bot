import os
import asyncio
from datetime import datetime, timedelta
from utils import SlackHelper, get_logger
from dotenv import load_dotenv
import pytz

load_dotenv()

CHANNEL = "general"
# CHANNEL = "ed-notifications"
SYS_ADMIN = os.getenv("SYS_ADMIN")
CHECK_INTERVAL = 60  # seconds
logger = get_logger("reminder_module")

REMINDER_MESSAGE = "Reminder to submit hours on Workday by 6PM!"
# REMINDER_MESSAGE = "test message"

async def main():
    slack = SlackHelper()
    logger.info("Initializing SlackHelper and starting reminder module.")
    # Notify SYS_ADMIN on startup
    admin_id = slack.find_user_id(SYS_ADMIN)
    if admin_id:
        slack.send_message(admin_id, "reminder_module started and running.")
        logger.info(f"Sent startup message to SYS_ADMIN: {SYS_ADMIN}")
    else:
        logger.error(f"Could not find Slack user for SYS_ADMIN: {SYS_ADMIN}")

    sent_this_week = False
    eastern = pytz.timezone("US/Eastern")
    while True:
        now = datetime.now(tz=eastern)
        logger.debug(f"Current time (Eastern): {now}, sent_this_week: {sent_this_week}")
        # Sunday is 6 (Monday=0, Sunday=6)
        if now.weekday() == 6 and now.hour == 16:
            if not sent_this_week:
                channel_id = slack.find_channel(CHANNEL)
                if channel_id:
                    slack.send_message(channel_id, REMINDER_MESSAGE)
                    logger.info(f"Sent reminder to channel {CHANNEL}.")
                else:
                    logger.error(f"Could not find Slack channel: {CHANNEL}")
                sent_this_week = True
        else:
            # Reset flag after Sunday 5PM
            if now.weekday() != 6 or now.hour > 17:
                if sent_this_week:
                    logger.debug("Resetting sent_this_week flag.")
                sent_this_week = False
        await asyncio.sleep(CHECK_INTERVAL)
        logger.debug("Sleeping for CHECK_INTERVAL seconds.")

if __name__ == "__main__":
    logger.info("Starting reminder module.")
    asyncio.run(main())

import os
import asyncio
from datetime import datetime, timedelta
from utils import SlackHelper, get_logger
from dotenv import load_dotenv

load_dotenv()

CHANNEL = "general"
SYS_ADMIN = os.getenv("SYS_ADMIN")
CHECK_INTERVAL = 60  # seconds
logger = get_logger("reminder_module")

REMINDER_MESSAGE = "Reminder to submit hours on Workday by 6PM!"

async def main():
    slack = SlackHelper()
    # Notify SYS_ADMIN on startup
    admin_id = slack.find_user_id(SYS_ADMIN)
    if admin_id:
        slack.send_message(admin_id, "reminder_module started and running.")
        logger.info(f"Sent startup message to SYS_ADMIN: {SYS_ADMIN}")
    else:
        logger.error(f"Could not find Slack user for SYS_ADMIN: {SYS_ADMIN}")

    sent_this_week = False
    while True:
        now = datetime.now()
        # Sunday is 6 (Monday=0, Sunday=6)
        if now.weekday() == 6 and now.hour == 16:
            if not sent_this_week:
                channel_id = slack.find_channel(CHANNEL)
                slack.send_message(channel_id, REMINDER_MESSAGE)
                logger.info(f"Sent reminder to {CHANNEL}")
                sent_this_week = True
        else:
            # Reset flag after Sunday 5PM
            if now.weekday() != 6 or now.hour > 17:
                sent_this_week = False
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())

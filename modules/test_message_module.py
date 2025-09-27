
import asyncio
from utils import SlackHelper, get_logger
from dotenv import load_dotenv
import os

load_dotenv()

USER_NAME = os.getenv("SYS_ADMIN")
REFRESH_INTERVAL = 30  # seconds
logger = get_logger("test_message_module")

async def main():
    slack = SlackHelper()
    user_id = slack.find_user_id(USER_NAME)
    if user_id:
        slack.send_message(user_id, "1600 Bot up and running!")
        logger.info(f"Sent DM to {USER_NAME} ({user_id})")
    else:
        logger.warning(f"User '{USER_NAME}' not found.")
    while True:
        await asyncio.sleep(REFRESH_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())

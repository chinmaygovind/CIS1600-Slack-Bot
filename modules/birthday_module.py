import os
import asyncio
import csv
from datetime import datetime, timedelta
from utils import SlackHelper, get_logger
from dotenv import load_dotenv

load_dotenv()

STAFF_CSV = os.getenv("STAFF_CSV", "config/staff.csv")
CHANNEL = os.getenv("BIRTHDAY_CHANNEL", "general")
CHECK_INTERVAL = int(os.getenv("BIRTHDAY_CHECK_INTERVAL", "600"))  # seconds
logger = get_logger("birthday_module")

# Suggestion: keep config files like staff.csv in a 'config/' folder at the project root

def load_staff_birthdays(csv_path):
    staff = []
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Expecting columns: name, birthday (YYYY-MM-DD)
            staff.append({
                'name': row['name'],
                'birthday': row['birthday']
            })
    return staff

def is_today_birthday(birthday_str):
    today = datetime.now().date()
    try:
        bday = datetime.strptime(birthday_str, "%Y-%m-%d").date()
        return bday.month == today.month and bday.day == today.day
    except Exception as e:
        logger.error(f"Invalid birthday format: {birthday_str} ({e})")
        return False

async def main():
    slack = SlackHelper()
    staff = load_staff_birthdays(STAFF_CSV)
    wished = set()
    while True:
        now = datetime.now()
        if now.hour == 0:  # 12am
            for member in staff:
                if is_today_birthday(member['birthday']) and member['name'] not in wished:
                    msg = f"Happy Birthday, {member['name']}! :tada:"
                    channel_id = slack.find_channel(CHANNEL)
                    slack.send_message(channel_id, msg)
                    logger.info(f"Sent birthday message for {member['name']} to {CHANNEL}")
                    wished.add(member['name'])
        # Reset wished set at midnight next day
        if now.hour == 1 and wished:
            wished.clear()
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())

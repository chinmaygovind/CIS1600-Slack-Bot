import os
import asyncio
import csv
from datetime import datetime, timedelta
from utils import SlackHelper, get_logger
from dotenv import load_dotenv

load_dotenv()

STAFF_CSV = os.getenv("STAFF_CSV", "config/staff.csv")
ADMINS = [admin.strip() for admin in os.getenv("BIRTHDAY_ADMINS", "chinmay govind").split(",")]
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
                'name': row['Name'],
                'birthday': row['Birthday']
            })
    return staff

def is_today_birthday(birthday_str):
    today = datetime.now().date()
    try:
        bday = datetime.strptime(birthday_str, "%m/%d/%Y").date()
        return bday.month == today.month and bday.day == today.day
    except Exception as e:
        logger.error(f"Invalid birthday format: {birthday_str} ({e})")
        return False

async def main():
    slack = SlackHelper()
    staff = load_staff_birthdays(STAFF_CSV)
    # Sort staff by birthday (month, day)
    def birthday_key(member):
        try:
            bday = datetime.strptime(member['birthday'], "%m/%d/%Y")
            return (bday.month, bday.day)
        except Exception:
            return (13, 32)  # Put invalid dates at the end
    staff.sort(key=birthday_key)
    wished = set()

    # Format birthday table as text
    table_header = f"{'Name':<20} | {'Birthday':<10}\n" + ("-" * 33)
    table_rows = [f"{member['name']:<20} | {member['birthday']:<10}" for member in staff]
    birthday_table = table_header + "\n" + "\n".join(table_rows)

    # Send birthday table to all admins on startup
    for admin in ADMINS:
        user_id = slack.find_user_id(admin)
        if user_id:
            slack.send_message(user_id, f"Staff Birthday List:\n{birthday_table}")
            logger.info(f"Sent birthday table to admin {admin}")
        else:
            logger.error(f"Could not find Slack user for admin: {admin}")

    while True:
        now = datetime.now()
        if now.hour == 0:  # 12am
            for member in staff:
                if is_today_birthday(member['birthday']) and member['name'] not in wished:
                    msg = f"It's {member['name']}'s birthday today! ({member['birthday']}) :tada:"
                    for admin in ADMINS:
                        user_id = slack.find_user_id(admin)
                        if user_id:
                            slack.send_message(user_id, msg)
                            logger.info(f"Sent birthday notification for {member['name']} to admin {admin}")
                        else:
                            logger.error(f"Could not find Slack user for admin: {admin}")
                    wished.add(member['name'])
        # Reset wished set at midnight next day
        if now.hour == 1 and wished:
            wished.clear()
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())

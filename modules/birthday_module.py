import os
import asyncio
import csv
from datetime import datetime, timedelta, date
from utils import SlackHelper, get_logger
from dotenv import load_dotenv

load_dotenv()

STAFF_CSV = os.getenv("STAFF_CSV", "config/staff.csv")
ADMINS = [admin.strip() for admin in os.getenv("ADMINS", "Chinmay Govind").split(",")]
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

def parse_birthday(birthday_str):
    try:
        return datetime.strptime(birthday_str, "%m/%d/%Y").date()
    except Exception as e:
        logger.error(f"Invalid birthday format: {birthday_str} ({e})")
        return None

def is_today_birthday(birthday_str):
    today = datetime.now().date()
    bday = parse_birthday(birthday_str)
    if bday is None:
        return False
    return bday.month == today.month and bday.day == today.day

def days_until_birthday(birthday_str, today):
    """Days from today until the next anniversary of this birthday (0 == today)."""
    bday = parse_birthday(birthday_str)
    if bday is None:
        return None
    def anniversary(year):
        try:
            return bday.replace(year=year)
        except ValueError:  # Feb 29 in a non-leap year
            return date(year, 3, 1)
    upcoming = anniversary(today.year)
    if upcoming < today:
        upcoming = anniversary(today.year + 1)
    return (upcoming - today).days

def find_next_birthday(staff, today):
    """The soonest birthday strictly after today. Ties break alphabetically."""
    upcoming = []
    for member in staff:
        days = days_until_birthday(member['birthday'], today)
        if days is not None and days > 0:
            upcoming.append((days, member['name'], member))
    if not upcoming:
        return None
    days, _, member = min(upcoming, key=lambda row: (row[0], row[1]))
    return days, member

def upcoming_birthdays(staff, today, count):
    """The next `count` birthdays after today, soonest first."""
    rows = []
    for member in staff:
        days = days_until_birthday(member['birthday'], today)
        if days is not None and days > 0:
            rows.append((days, member['name'], member))
    rows.sort(key=lambda row: (row[0], row[1]))
    return [(days, member) for days, _, member in rows[:count]]

def build_startup_message(staff, today):
    lines = ["*1600 Bot birthday module initialized!* :tada:"]

    todays = [member for member in staff if is_today_birthday(member['birthday'])]
    if todays:
        lines.append(f":birthday: *Today:* {', '.join(m['name'] for m in todays)}")

    upcoming = upcoming_birthdays(staff, today, 3)
    if upcoming:
        days, member = upcoming[0]
        plural = "" if days == 1 else "s"
        lines.append(
            f"*Next birthday:* {member['name']} ({member['birthday']}) - in {days} day{plural}"
        )
        if len(upcoming) > 1:
            rest = ", ".join(f"{m['name']} ({d}d)" for d, m in upcoming[1:])
            lines.append(f"*Then:* {rest}")
    else:
        lines.append("No upcoming birthdays on file.")

    lines.append(
        f"_Tracking {len(staff)} staff from {STAFF_CSV}. "
        f"Checking every {CHECK_INTERVAL}s; announcements go out at midnight._"
    )
    return "\n".join(lines)

async def main():
    slack = SlackHelper("birthday_module")
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

    # Send a short status summary to all admins on startup
    startup_message = build_startup_message(staff, datetime.now().date())
    for admin in ADMINS:
        user_id = slack.find_user_id(admin)
        if user_id:
            slack.send_message(user_id, startup_message)
            logger.info(f"Sent startup summary to admin {admin}")
        else:
            logger.error(f"Could not find Slack user for admin: {admin}")

    while True:
        now = datetime.now()
        if now.hour == 0:  # 12am
            for member in staff:
                if is_today_birthday(member['birthday']) and member['name'] not in wished:
                    msg = f"It's {member['name']}'s birthday today! ({member['birthday']}) :tada:"
                    nxt = find_next_birthday(staff, now.date())
                    if nxt:
                        days, next_member = nxt
                        plural = "" if days == 1 else "s"
                        msg += (
                            f"\nNext birthday: {next_member['name']} "
                            f"({next_member['birthday']}) - in {days} day{plural}"
                        )
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


import os
import asyncio




import os
import asyncio
import re
from edapi import EdAPI
from utils import SlackHelper, get_logger
from dotenv import load_dotenv


load_dotenv()

REGION = os.getenv("ED_REGION")
COURSE_ID = int(os.getenv("ED_COURSE_ID"))
ED_API_KEY = os.getenv("ED_API_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "ed-notifications")
REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL_SECONDS", "10"))
logger = get_logger("ed_module")

def get_link_from_id(id):
    return f"https://edstem.org/{REGION}/courses/{COURSE_ID}/discussion/" + str(id)

def get_max_thread_number(ed):
    threads = ed.list_threads(course_id=COURSE_ID, limit=100, sort="new")
    threads.sort(key=lambda thread: thread["number"], reverse=True)
    latest_thread = threads[0]
    return latest_thread["number"], latest_thread["id"]

async def main():
    slack = SlackHelper()
    ed = EdAPI()
    channel_id = slack.find_channel(SLACK_CHANNEL)
    last_thread, _ = get_max_thread_number(ed)
    slack.send_message(channel_id, "EdModule initialized!")
    while True:
        try:
            updated_last_thread, id = get_max_thread_number(ed)
            thread = ed.get_thread(id)
            thread_title = thread["title"]
            thread_content = thread["content"]
            # Convert common Ed HTML tags to Slack formatting
            def ed_html_to_slack(text):
                # Replace paragraphs with newlines
                text = re.sub(r'</?paragraph>', '\n', text)
                # Replace <b> and <strong> with *bold*
                text = re.sub(r'<(/)?(bold|strong)>', '*', text)
                # Replace <i> and <em> with _italic_
                text = re.sub(r'<(/)?(italic|em)>', '_', text)
                # Replace <code> with backticks
                text = re.sub(r'<code>', '`', text)
                text = re.sub(r'</code>', '`', text)
                # Replace <pre> with triple backticks
                text = re.sub(r'<pre>', '```', text)
                text = re.sub(r'</pre>', '```', text)
                # Remove <document> tags
                text = re.sub(r'</?document[^>]*>', '', text)
                # Remove any remaining tags (optional, or leave as is)
                return text.strip()

            formatted_content = ed_html_to_slack(thread_content)
            if updated_last_thread > last_thread:
                message = (
                    f"*New Ed Post (#{updated_last_thread}): {thread_title}*\n"
                    f"{formatted_content}\n"
                    f"Link: {get_link_from_id(id)}"
                )
                slack.send_message(channel_id, message)
                last_thread = updated_last_thread
                logger.info(f"New thread, sent message {message}")
            # logger.info(f"last seen thread: {last_thread} with link {get_link_from_id(id)}. Title: {thread_title}")
            await asyncio.sleep(REFRESH_INTERVAL)
        except Exception as e:
            logger.error(f"Error in EdModule: {e}")
            await asyncio.sleep(REFRESH_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())

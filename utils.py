import os
import logging
from slack_sdk import WebClient
from dotenv import load_dotenv

# Set up logging with module name

def get_logger(module_name):
    logger = logging.getLogger(module_name)
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [{module_name}] %(levelname)s: %(message)s"
    )
    return logger

class SlackHelper:
    def __init__(self):
        load_dotenv()
        self.token = os.getenv("SLACK_API_TOKEN")
        self.client = WebClient(token=self.token)

    def send_message(self, channel, body):
        self.client.chat_postMessage(channel=channel, text=body)

    def find_channel(self, channel_name):
        channels = self.client.conversations_list(types="public_channel,private_channel")["channels"]
        for channel in channels:
            if channel["name_normalized"] == channel_name:
                return channel["id"]
        return None

    def find_user_id(self, real_name):
        users = self.client.users_list()["members"]
        for user in users:
            if user.get("real_name") == real_name:
                return user["id"]
        return None

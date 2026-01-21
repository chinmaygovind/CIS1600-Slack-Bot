import os
import logging
from slack_sdk import WebClient
from dotenv import load_dotenv

# Set up logging with module name

import datetime

def get_logger(module_name):
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "slackbot.log")
    
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.INFO)

    # Prevent adding handlers multiple times
    if not logger.handlers:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        formatter = logging.Formatter(f"%(asctime)s [{module_name}] %(levelname)s: %(message)s")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Also log to console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    return logger

class SlackHelper:
    def __init__(self, module_name):
        load_dotenv()
        self.logger = get_logger(module_name)
        self.token = os.getenv("SLACK_API_TOKEN")
        self.client = WebClient(token=self.token)

    def send_message(self, channel, body):
        self.logger.info(f"Sending message to channel {channel}")
        self.client.chat_postMessage(channel=channel, text=body)

    def find_channel(self, channel_name):
        self.logger.info(f"Finding channel: {channel_name}")
        channels = self.client.conversations_list(types="public_channel,private_channel")["channels"]
        for channel in channels:
            if channel["name_normalized"] == channel_name:
                self.logger.info(f"Found channel {channel_name} with id {channel['id']}")
                return channel["id"]
        self.logger.warning(f"Could not find channel: {channel_name}")
        return None

    def find_user_id(self, real_name):
        self.logger.info(f"Finding user id for: {real_name}")
        users = self.client.users_list()["members"]
        for user in users:
            if user.get("real_name") == real_name:
                self.logger.info(f"Found user id {user['id']} for {real_name}")
                return user["id"]
        self.logger.warning(f"Could not find user id for: {real_name}")
        return None

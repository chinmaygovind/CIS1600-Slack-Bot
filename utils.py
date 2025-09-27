import os
import logging
from slack_sdk import WebClient
from dotenv import load_dotenv

# Set up logging with module name

import datetime

def get_logger(module_name):
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.INFO)
    # Create logs/module_name/ if it doesn't exist
    log_dir = os.path.join("logs", module_name)
    os.makedirs(log_dir, exist_ok=True)
    # Log file name: START_TIME.log (YYYYMMDD_HHMMSS)
    start_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(log_dir, f"{start_time}.log")
    # Remove any existing handlers to avoid duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()
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

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

    def send_message(self, channel, body, thread_ts=None):
        """Post a message; returns its `ts` so replies can be threaded under it."""
        self.logger.info(f"Sending message to channel {channel}")
        response = self.client.chat_postMessage(
            channel=channel, text=body, thread_ts=thread_ts
        )
        return response.get("ts")

    def upload_images(self, channel, paths, thread_ts=None, comment=None):
        """Upload PNGs into a thread. Needs the `files:write` scope.

        Slack ignores `initial_comment` on all but the first upload, so the
        comment is attached once and the rest follow as bare images.
        """
        uploaded = 0
        for index, path in enumerate(paths):
            try:
                self.client.files_upload_v2(
                    channel=channel,
                    thread_ts=thread_ts,
                    file=path,
                    title=os.path.basename(path),
                    initial_comment=comment if index == 0 else None,
                )
                uploaded += 1
            except Exception as e:
                self.logger.error(f"Failed to upload {path}: {e}")
        return uploaded

    def dm(self, real_name, body):
        user_id = self.find_user_id(real_name)
        if not user_id:
            self.logger.error(f"Could not DM {real_name}: no such Slack user")
            return False
        try:
            self.client.chat_postMessage(channel=user_id, text=body)
            return True
        except Exception as e:
            self.logger.error(f"Could not DM {real_name}: {e}")
            return False

    def dm_admins(self, body):
        """DM everyone in ADMINS. Used to surface failures nobody would see."""
        admins = [a.strip() for a in os.getenv("ADMINS", "").split(",") if a.strip()]
        if not admins:
            self.logger.warning("ADMINS is not set; cannot send alert")
        for admin in admins:
            self.dm(admin, body)

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

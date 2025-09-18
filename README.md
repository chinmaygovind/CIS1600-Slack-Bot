# CIS1600 Slack Bot

This bot monitors Ed Discussion posts for your CIS1600 course and sends notifications to a Slack channel.

## Features
- Converts Ed HTML to Slack formatting using `html-slacker`
- Notifies Slack channel of new Ed posts
- Configurable via `.env` file

## Setup Instructions

### 1. Clone the Repository
```
git clone https://github.com/chinmaygovind/CIS1600-Slack-Bot.git
cd CIS1600-Slack-Bot
```

### 2. Install Python and pip
- On Amazon Linux:
  ```bash
  sudo yum update -y
  sudo yum install python3 python3-pip -y
  ```
- On Ubuntu:
  ```bash
  sudo apt update
  sudo apt install python3 python3-pip -y
  ```

### 3. Install Dependencies
```
pip3 install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the project root with your credentials:
```
ED_API_TOKEN=your_ed_api_token
ED_REGION=us
ED_COURSE_ID=your_course_id
SLACK_API_TOKEN=your_slack_api_token
SLACK_CHANNEL=ed-notifications
REFRESH_INTERVAL_SECONDS=10
```

### 5. Run the Bot

#### On Windows (using batch script):
Use the provided batch script to run any module and save logs automatically:
```
run_module.bat ed_module
```
This will run the module in the background and save logs to `logs/ed_module_logs_<date>.log`.
You can replace `ed_module` with any other module name (e.g., `birthday_module`).


#### On Linux/EC2 (using shell script):
Use the provided shell script to run any module and save logs automatically:
```
chmod +x run_module.sh
./run_module.sh ed_module
```
This will run the module in the background and save logs to `logs/ed_module_logs_<date>.log`.
You can replace `ed_module` with any other module name (e.g., `birthday_module`).

### 6. View Logs
To view the logs:
```
tail -f logs/ed_bot_logs_YYYY_MM_DD.log
```

## Troubleshooting
- If you see `python: command not found`, install Python as shown above.
- If you see `pip: command not found`, install pip as shown above.
- If you see `ImportError: No module named html_slacker`, run:
  ```
  pip3 install html-slacker
  ```
- Make sure your `.env` file is not tracked by git (add `.env` to `.gitignore`).

## License
MIT

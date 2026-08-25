# CIS1600 Slack Bot

This bot has utilities to help the CIS 1600 Slack.

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
Create a `.env` file in the project root with your credentials.

#### General
- `SLACK_API_TOKEN`: Your Slack API token for the bot to communicate with Slack.

#### Ed Module (`ed_module.py`)
- `ED_API_TOKEN`: Your Ed Discussion API token.
- `ED_REGION`: The region for your Ed Discussion instance (e.g., `us`).
- `ED_COURSE_ID`: The ID of your course on Ed Discussion.
- `SLACK_CHANNEL`: The Slack channel for Ed notifications (e.g., `ed-notifications`).
- `REFRESH_INTERVAL_SECONDS`: How often to check for new posts (e.g., `10`).

#### Birthday Module (`birthday_module.py`)
- `ADMINS`: A comma-separated list of Slack display names (the profile `real_name`, matched exactly) to notify (e.g. `Chinmay Govind,David Fu`).


### 5. Orchestrator: Manage All Bots

Use the orchestrator CLI to view, start, and stop all modules from one place.

#### Start the orchestrator:
```
python orchestrator.py
```

#### Orchestrator commands:
- `status` — Show status of all modules (running/stopped, PID, start time, file modified)
- `start X` — Start module number X (from status table)
- `start all` — Start all modules
- `stop X` — Stop module number X (from status table)
- `stop all` — Stop all modules
- `help` — Show all commands
- `exit` — Exit the orchestrator

#### Add a new module to orchestrator:
1. Create your module in the `modules/` folder (e.g., `modules/reminder_module.py`).
2. Add the module name (without `.py`) to the `MODULES` list in `orchestrator.py`:
   ```python
   MODULES = [
     "ed_module",
     "birthday_module",
     "test_message_module",
     "reminder_module"
   ]
   ```
3. Save and re-run `python orchestrator.py`. The new module will appear in the CLI.

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

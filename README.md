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

#### Homework Attachments (`hw_pdfs.py`, used by `ed_module.py`)
When a new Ed post can be tied to a specific homework problem, the bot replies in
that Slack message's thread with the problem as it appears in the homework PDF,
followed by its solution.

- `OVERLEAF_PROJECT_ID`: The Overleaf project id (the hex string in the project URL).
- `OVERLEAF_GIT_TOKEN`: An Overleaf git token (Account Settings -> Git integration).
  Requires an Overleaf paid plan.
- `HW_SYNC_INTERVAL_HOURS`: How often to `git pull` and rebuild (default `12`).
- `HW_ATTACH_ENABLED`: Set to `false` to post Ed notifications without attachments.
- `HW_RENDER_DPI`: PNG render resolution (default `110`).
- `HW_MAX_PAGES`: Cap on pages attached per problem (default `4`).

This needs two system packages and one extra Slack scope:

```bash
sudo apt install texlive-latex-extra latexmk poppler-utils   # Ubuntu
```

The Slack app needs the **`files:write`** scope to upload the images, in addition
to the scopes it already has. Failures (Overleaf unreachable, a homework that
will not build, an upload that is rejected) are DM'd to `ADMINS` and never block
the Ed notification itself.

Built PDFs and PNGs are cached under `cache/`, which is gitignored.

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

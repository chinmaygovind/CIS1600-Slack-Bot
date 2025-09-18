#!/bin/bash
# Usage: ./kill_bots.sh

# Kill all running python modules in CIS1600SlackBot (ed_module, birthday_module, test_message_module, slack_bot, etc)

pkill -f 'python3 -m modules.'

# Optionally, show remaining running python processes
ps aux | grep '[p]ython3'

echo "All CIS1600 Slack bot processes have been killed."

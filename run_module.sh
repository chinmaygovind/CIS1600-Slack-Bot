#!/bin/bash
# Usage: ./run_module.sh <module_name>

MODULE="$1"
if [ -z "$MODULE" ]; then
    echo "Please provide a module name. Example: birthday_module"
    exit 1
fi

DATE=$(date +%Y_%m_%d)

mkdir -p logs
nohup python3 -m modules.$MODULE > logs/${MODULE}_logs_${DATE}.log 2>&1 &

echo "Started modules.$MODULE with logs in logs/${MODULE}_logs_${DATE}.log"

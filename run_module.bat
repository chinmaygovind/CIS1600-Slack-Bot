@echo off
REM Usage: run_module.bat <module_name>

set MODULE=%1
if "%MODULE%"=="" (
    echo Please provide a module name. Example: birthday_module
    exit /b 1
)

REM Get current date in YYYY_MM_DD format
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do set DATE=%%c_%%a_%%b
REM If your system uses a different date format, adjust the tokens above

REM Create logs directory if it doesn't exist
if not exist logs mkdir logs

REM Run the module with nohup-like behavior (Windows doesn't have nohup, so use start)
start /b python3 -m modules.%MODULE% > logs/%MODULE%_logs_%DATE%.log 2>&1

echo Started modules.%MODULE% with logs in logs/%MODULE%_logs_%DATE%.log

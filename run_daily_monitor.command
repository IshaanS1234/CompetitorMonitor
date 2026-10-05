#!/bin/zsh

MONITOR_PROJECT_DIR=${0:A:h}
/bin/mkdir -p "$MONITOR_PROJECT_DIR/automation_logs"
printf 'macOS handed the scheduled run to Terminal at %s.\n' "$(/bin/date)" >>"$MONITOR_PROJECT_DIR/automation_logs/terminal_handoff.log"

exec /bin/zsh "$MONITOR_PROJECT_DIR/run_daily_monitor.sh"

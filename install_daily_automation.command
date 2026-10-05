#!/bin/zsh

set -e

MONITOR_PROJECT_DIR=${0:A:h}
MONITOR_LABEL="com.ishaansharma.competitor-monitor"
MONITOR_SOURCE="$MONITOR_PROJECT_DIR/$MONITOR_LABEL.plist"
MONITOR_DESTINATION="$HOME/Library/LaunchAgents/$MONITOR_LABEL.plist"
MONITOR_COMMAND="$MONITOR_PROJECT_DIR/run_daily_monitor.command"
MONITOR_USER_ID=$(/usr/bin/id -u)

echo "Installing the 3:00 PM competitor monitor..."

/bin/mkdir -p "$HOME/Library/LaunchAgents"
/usr/bin/install -m 644 "$MONITOR_SOURCE" "$MONITOR_DESTINATION"
/usr/bin/plutil -replace ProgramArguments.4 -string "$MONITOR_COMMAND" "$MONITOR_DESTINATION"

/bin/launchctl bootout "gui/$MONITOR_USER_ID/$MONITOR_LABEL" 2>/dev/null || true
/bin/launchctl bootstrap "gui/$MONITOR_USER_ID" "$MONITOR_DESTINATION"
/bin/launchctl enable "gui/$MONITOR_USER_ID/$MONITOR_LABEL"

echo ""
echo "Automation installed successfully."
echo "It will run daily at 3:00 PM and catch up after login or waking."
echo ""
echo "You may close this window."

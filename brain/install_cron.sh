#!/bin/bash
# install_cron.sh — Wire the Apex Brain to macOS cron
# Von Descieux / Descieux Digital
#
# WHAT THIS DOES:
#   Installs a cron job that runs apex_brain.py --cycle every 15 minutes
#   during business hours (7 AM – 10 PM).
#
# USAGE:
#   cd ~/apex-ai-orchestrator
#   chmod +x brain/install_cron.sh
#   ./brain/install_cron.sh
#
# TO REMOVE:
#   crontab -l | grep -v apex_brain | crontab -

set -e

REPO="$HOME/apex-ai-orchestrator"
PYTHON=$(which python3)
LOG="$REPO/memory/cron.log"

# Verify files exist
if [ ! -f "$REPO/apex_brain.py" ]; then
  echo "ERROR: $REPO/apex_brain.py not found. Run from ~/apex-ai-orchestrator."
  exit 1
fi

# Check for ANTHROPIC_API_KEY
if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "WARNING: ANTHROPIC_API_KEY not set in current shell."
  echo "         Make sure it's in your ~/.zshrc or ~/.bashrc so cron can find it."
  echo "         Example: export ANTHROPIC_API_KEY=sk-ant-..."
fi

# Build cron entry
# Runs every 15 min, 7AM–10PM, quiet mode, logs to file
CRON_CMD="*/15 7-21 * * * cd $REPO && ANTHROPIC_API_KEY=\$ANTHROPIC_API_KEY $PYTHON apex_brain.py --cycle --quiet >> $LOG 2>&1"

echo "Installing cron job:"
echo "  $CRON_CMD"
echo ""

# Add to crontab (avoid duplicates)
(crontab -l 2>/dev/null | grep -v "apex_brain"; echo "$CRON_CMD") | crontab -

echo "✓ Cron job installed."
echo ""
echo "To verify:"
echo "  crontab -l"
echo ""
echo "To remove:"
echo "  crontab -l | grep -v apex_brain | crontab -"
echo ""
echo "Log file: $LOG"
echo ""
echo "NEXT STEPS:"
echo "  1. Test manually first:"
echo "     python apex_brain.py --cycle --dry-run"
echo ""
echo "  2. Check status:"
echo "     python apex_brain.py --status"
echo ""
echo "  3. Issue a command:"
echo "     python apex_brain.py \"Run DataTech SEG-1 campaign\""

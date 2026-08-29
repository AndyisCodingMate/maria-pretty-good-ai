#!/bin/bash
# Starts both the server and tunnel in one terminal.
# After tunnel URL appears, update .env and make your call.

cd ~/pretty_good_AI_project

echo "Starting server on port 8000..."
python3 main.py &
SERVER_PID=$!
sleep 2

# Check server started
if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo "Server failed to start. Check dependencies."
    exit 1
fi

echo "Server running (PID $SERVER_PID)"
echo ""
echo "Starting cloudflared tunnel..."
~/.local/bin/cloudflared tunnel --url http://localhost:8000 &
TUNNEL_PID=$!
sleep 5

echo ""
echo "============================================"
echo "  BOTH RUNNING — Make your call now"
echo "  Press Ctrl+C to stop both"
echo "============================================"

# Wait for Ctrl+C, then clean up
trap "kill $SERVER_PID $TUNNEL_PID 2>/dev/null; echo ''; echo 'Stopped.'; exit 0" SIGINT SIGTERM
wait

#!/bin/bash

# Kill any existing ngrok processes
pkill ngrok || true

# Start ngrok using the configuration file
ngrok start --config /app/ngrok.yml app &
sleep 2
ngrok_url=$(curl -s http://localhost:4040/api/tunnels | grep -o "https://.*ngrok-free.app")
echo "Ngrok URL: $ngrok_url"

# Start Flask application
flask run --host 0.0.0.0 --port 3001 
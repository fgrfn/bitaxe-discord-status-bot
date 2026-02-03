#!/bin/bash

# BitAxe Discord Bot Starter Script

echo "🤖 Starting BitAxe Discord Bot..."

# Check if config.ini exists
if [ ! -f "config.ini" ]; then
    echo "❌ config.ini not found!"
    echo "📋 Please copy config.ini.example to config.ini and configure it."
    echo "   cp config.ini.example config.ini"
    exit 1
fi

# Check if virtual environment should be used
if [ -d "venv" ]; then
    echo "🐍 Activating virtual environment..."
    source venv/bin/activate
fi

# Start the bot
python -m src.main

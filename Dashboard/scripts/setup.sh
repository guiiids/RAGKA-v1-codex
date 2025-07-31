#!/bin/bash

# Agilent Chatbot Tools - Setup Script
# This script sets up the development environment and starts the application

echo "🚀 Setting up Agilent Chatbot Tools Dashboard..."
echo "================================================"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check Python version
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ Python $python_version detected"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip is not installed. Please install pip."
    exit 1
fi

echo "✅ pip detected"

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

# Start the application
echo "🌟 Starting the Agilent Chatbot Tools Dashboard..."
echo "================================================"
echo "🌐 The application will be available at: http://localhost:5001"
echo "🛑 Press Ctrl+C to stop the server"
echo ""

python3 app.py


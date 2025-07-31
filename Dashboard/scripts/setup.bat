@echo off
REM Agilent Chatbot Tools - Setup Script for Windows
REM This script sets up the development environment and starts the application

echo 🚀 Setting up Agilent Chatbot Tools Dashboard...
echo ================================================

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed. Please install Python 3.8 or higher.
    pause
    exit /b 1
)

echo ✅ Python detected

REM Check if pip is installed
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ pip is not installed. Please install pip.
    pause
    exit /b 1
)

echo ✅ pip detected

REM Install dependencies
echo 📦 Installing dependencies...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)

echo ✅ Dependencies installed successfully

REM Start the application
echo 🌟 Starting the Agilent Chatbot Tools Dashboard...
echo ================================================
echo 🌐 The application will be available at: http://localhost:5001
echo 🛑 Press Ctrl+C to stop the server
echo.

python app.py

pause


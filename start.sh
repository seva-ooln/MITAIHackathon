#!/bin/bash

echo "🚀 Starting Voice Meeting Bot with Zoom Integration"
echo "=================================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  Creating .env file from template..."
    cp .env.template .env
    echo "✅ Created .env file. Please edit it with your API keys:"
    echo "   - ASSEMBLYAI_API_KEY"
    echo "   - OPENAI_API_KEY"
    echo "   - ZOOM_APP_CLIENT_ID (optional for testing)"
    echo "   - ZOOM_APP_CLIENT_SECRET (optional for testing)"
    echo ""
    echo "Edit .env file and run this script again."
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

echo "🐳 Building Docker containers..."
docker-compose build

if [ $? -eq 0 ]; then
    echo "✅ Build successful!"
    echo ""
    echo "Choose how to run the system:"
    echo "1) Full system (API + Integration Bridge)"
    echo "2) Integration Bridge only"
    echo "3) API service only"
    echo "4) Mock testing mode"
    echo ""
    read -p "Enter your choice (1-4): " choice

    case $choice in
        1)
            echo "🚀 Starting full system..."
            docker-compose up
            ;;
        2)
            echo "🔗 Starting Integration Bridge..."
            docker-compose run --rm --service-ports voice-meeting-bot python zoom_integration_bridge.py
            ;;
        3)
            echo "🌐 Starting API service..."
            docker-compose up api-service
            ;;
        4)
            echo "🎭 Starting in mock testing mode..."
            docker-compose run --rm voice-meeting-bot python -c "
import asyncio
from zoom_integration_bridge import main
print('Starting mock meeting for testing...')
asyncio.run(main())
"
            ;;
        *)
            echo "Invalid choice. Starting full system..."
            docker-compose up
            ;;
    esac
else
    echo "❌ Build failed. Please check the error messages above."
    exit 1
fi
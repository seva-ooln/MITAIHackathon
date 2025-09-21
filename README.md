# Voice Meeting Bot with Zoom Integration

An AI-powered meeting facilitator that joins Zoom meetings to provide real-time speaker identification, conversation analysis, and meeting facilitation.

## Features

- **Real-time Speaker Identification**: Uses AssemblyAI to identify and map speakers during meetings
- **Meeting Facilitation**: AI bot that guides introductions and facilitates discussions
- **Zoom Integration**: Seamlessly joins Zoom meetings using the Zoom SDK
- **Conversation Analysis**: Extracts key points, action items, and decisions
- **REST API**: Complete API for programmatic meeting management
- **Docker Support**: Fully containerized for easy deployment

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Zoom Meeting  │◄──►│ Integration      │◄──►│ Voice Meeting   │
│   (Audio)       │    │ Bridge           │    │ Bot             │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │ py-zoom-meeting- │    │ AssemblyAI      │
                       │ sdk              │    │ Transcription   │
                       └──────────────────┘    └─────────────────┘
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- AssemblyAI API key
- OpenAI API key
- Zoom App credentials (for production)

### Setup

1. **Clone and navigate to the project**:
   ```bash
   cd /path/to/MITHackathon
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.template .env
   # Edit .env with your API keys
   ```

3. **Build and run with Docker**:
   ```bash
   # Build the unified container
   docker-compose build

   # Start the services
   docker-compose up
   ```

4. **Access the services**:
   - API Service: http://localhost:8001
   - Integration Bridge: Running on port 8000
   - API Documentation: http://localhost:8001/docs

## Usage

### Option 1: Direct Integration (Recommended)

Run the integration bridge directly to join Zoom meetings:

```bash
# In Docker container
docker-compose exec voice-meeting-bot python zoom_integration_bridge.py

# Or locally
python zoom_integration_bridge.py
```

### Option 2: REST API

Use the API to programmatically manage meetings:

```bash
# Start analyzing a meeting
curl -X POST "http://localhost:8001/meetings/start" \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_url": "https://zoom.us/j/123456789",
    "meeting_password": "password123",
    "expected_participants": ["Seva", "Sid", "Omar"]
  }'

# Check meeting status
curl "http://localhost:8001/meetings/{meeting_id}/status"

# Get conversation history
curl "http://localhost:8001/meetings/{meeting_id}/conversation"

# Stop meeting and get summary
curl -X POST "http://localhost:8001/meetings/{meeting_id}/stop"
```

### Option 3: Testing Mode

For development and testing without real Zoom meetings:

```bash
# Start mock meeting
curl -X POST "http://localhost:8001/test/mock-meeting"

# Or test speaker identification only
python test_assemblyai_bot.py --mode speaker
```

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# Voice Bot Environment Variables
ASSEMBLYAI_API_KEY=your_assemblyai_key
OPENAI_API_KEY=your_openai_key

# Zoom SDK Environment Variables (for production)
ZOOM_APP_CLIENT_ID=your_zoom_client_id
ZOOM_APP_CLIENT_SECRET=your_zoom_client_secret
MEETING_URLS=your_meeting_urls
```

### Bot Configuration

The bot behavior can be customized in `voice_meeting_bot.py`:

- `bot_name`: Name of the facilitator bot
- `introduction_timeout`: How long to wait for introductions
- `response_triggers`: Keywords that trigger bot responses

## Project Structure

```
├── src/                          # Core voice bot modules
│   ├── voice_meeting_bot.py      # Main bot logic
│   ├── speech_transcriber.py     # AssemblyAI integration
│   └── ...
├── py-zoom-meeting-sdk/          # Zoom SDK integration
├── zoom_integration_bridge.py    # Bridge between Zoom and voice bot
├── api_service.py               # REST API service
├── docker-compose.yml           # Docker orchestration
├── Dockerfile                   # Unified container
├── requirements.txt             # Python dependencies
└── test_*.py                    # Test scripts
```

## Development

### Local Development

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run tests**:
   ```bash
   # Test voice bot only
   python test_voice_bot.py

   # Test with AssemblyAI
   python test_assemblyai_bot.py

   # Test speaker identification only
   python test_assemblyai_bot.py --mode speaker
   ```

3. **Run integration bridge**:
   ```bash
   python zoom_integration_bridge.py
   ```

### Docker Development

```bash
# Build development image
docker-compose build

# Run with volume mounting for live editing
docker-compose up

# Execute commands in container
docker-compose exec voice-meeting-bot bash
```

## Deployment

### Cloud Run (Recommended)

1. **Build for production**:
   ```bash
   docker build -t voice-meeting-bot .
   ```

2. **Deploy to Cloud Run**:
   ```bash
   gcloud run deploy voice-meeting-bot \
     --image voice-meeting-bot \
     --platform managed \
     --region us-central1 \
     --set-env-vars ASSEMBLYAI_API_KEY=$ASSEMBLYAI_API_KEY
   ```

### Traditional Server

```bash
# Run with Docker Compose in production mode
docker-compose -f docker-compose.yml up -d
```

## API Documentation

Once running, visit http://localhost:8001/docs for complete API documentation with interactive testing.

### Key Endpoints

- `POST /meetings/start` - Start meeting analysis
- `GET /meetings/{id}/status` - Get meeting status
- `GET /meetings/{id}/conversation` - Get conversation history
- `POST /meetings/{id}/stop` - Stop analysis and get summary
- `POST /test/mock-meeting` - Start mock meeting for testing

## Troubleshooting

### Audio Issues

- Ensure microphone permissions are granted
- Check volume levels with test scripts
- Verify AssemblyAI API key is valid

### Zoom SDK Issues

- Ensure Docker has necessary system dependencies
- Check Zoom app credentials
- Verify meeting URL format

### Docker Issues

```bash
# Clean rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up

# Check logs
docker-compose logs voice-meeting-bot
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and test thoroughly
4. Submit a pull request

## License

MIT License - see LICENSE file for details
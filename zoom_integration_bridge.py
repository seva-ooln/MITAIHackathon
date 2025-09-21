#!/usr/bin/env python3
"""
Bridge between py-zoom-meeting-sdk and voice meeting bot
Integrates Zoom audio capture with speaker identification and analysis
"""
import asyncio
import json
import os
import sys
from typing import Dict, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass

# Add py-zoom-meeting-sdk to path
sys.path.append('../py-zoom-meeting-sdk')

from src.voice_meeting_bot import VoiceMeetingFacilitatorBot
from src.speech_transcriber import TranscriptionEvent


@dataclass
class ZoomAudioData:
    """Audio data from Zoom SDK"""
    participant_id: str
    participant_name: str
    audio_data: bytes
    timestamp: datetime
    sample_rate: int = 16000


class ZoomMeetingAnalyzer:
    """Integrates Zoom SDK with voice meeting analysis"""

    def __init__(self):
        self.meeting_bot = VoiceMeetingFacilitatorBot()
        self.zoom_client = None
        self.is_analyzing = False
        self.current_meeting_id = None

        # Audio processing
        self.audio_processor = None
        self.participant_audio_streams = {}

        # Callbacks for sending responses back to Zoom
        self.zoom_chat_callback: Optional[Callable[[str], None]] = None
        self.zoom_audio_callback: Optional[Callable[[str], None]] = None

    async def start_zoom_analysis(self,
                                meeting_url: str,
                                meeting_password: str = None,
                                expected_participants: List[str] = None) -> Dict[str, str]:
        """Start analysis for a Zoom meeting"""

        print(f"🔗 Starting Zoom meeting analysis")
        print(f"📹 Meeting URL: {meeting_url}")

        try:
            # Extract meeting ID from URL
            self.current_meeting_id = self._extract_meeting_id(meeting_url)

            # Initialize voice meeting bot
            result = await self.meeting_bot.join_meeting_with_voice(
                meeting_id=self.current_meeting_id,
                notes_file_path="temp/zoom_meeting_notes.json",  # Provide default notes file
                meeting_topic="Zoom Meeting Analysis",
                participants=expected_participants or []
            )

            if result["status"] != "success":
                return {"status": "error", "message": f"Failed to initialize meeting bot: {result['message']}"}

            # Disable bot's own transcription (Zoom provides audio)
            if self.meeting_bot.transcription_active:
                self.meeting_bot.transcriber.stop_transcription()

            # Connect to Zoom meeting
            zoom_result = await self._connect_to_zoom(meeting_url, meeting_password)

            if zoom_result["success"]:
                self.is_analyzing = True

                # Set up audio processing
                self._setup_zoom_audio_processing()

                # Send initial bot message to Zoom chat
                await self._send_introduction_message()

                return {
                    "status": "success",
                    "meeting_id": self.current_meeting_id,
                    "message": "Bot connected to Zoom meeting and ready for analysis"
                }
            else:
                return {"status": "error", "message": f"Failed to connect to Zoom: {zoom_result['error']}"}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _connect_to_zoom(self, meeting_url: str, password: str = None) -> Dict:
        """Connect to Zoom meeting using py-zoom-meeting-sdk"""

        print("🔌 Connecting to Zoom using SDK...")

        try:
            # Import the working bot class
            import sys
            sys.path.append('py-zoom-meeting-sdk')
            from bot import JoinOnlyBot

            # Initialize the working Zoom bot
            self.zoom_client = JoinOnlyBot()

            # Initialize and start the Zoom bot (it will read environment variables for meeting details)
            self.zoom_client.init()
            # Note: run_loop() is blocking, so we'll need to run it in a separate thread
            import threading
            zoom_thread = threading.Thread(target=self.zoom_client.run_loop, daemon=True)
            zoom_thread.start()

            print("✅ Successfully started Zoom bot")
            return {"success": True}

        except ImportError as e:
            # Fallback if SDK structure is different
            print(f"⚠️ Could not import Zoom SDK: {e} - using mock connection")
            return await self._mock_zoom_connection()
        except Exception as e:
            print(f"❌ Error connecting to Zoom: {e}")
            return {"success": False, "error": str(e)}

    async def _mock_zoom_connection(self) -> Dict:
        """Mock Zoom connection for testing without actual SDK"""
        print("🎭 Using mock Zoom connection for testing")

        # Simulate successful connection
        await asyncio.sleep(1)

        # Set up mock audio callbacks
        asyncio.create_task(self._simulate_zoom_audio())

        return {"success": True}

    async def _simulate_zoom_audio(self):
        """Simulate Zoom audio for testing"""
        print("🎤 Simulating Zoom audio streams...")

        # Simulate participants joining and speaking
        participants = [
            {"id": "participant_1", "name": "Seva"},
            {"id": "participant_2", "name": "Sid"},
            {"id": "participant_3", "name": "Omar"}
        ]

        await asyncio.sleep(3)  # Wait for setup

        # Simulate introductions
        for participant in participants:
            await asyncio.sleep(2)

            # Simulate audio data with introduction
            audio_data = ZoomAudioData(
                participant_id=participant["id"],
                participant_name=participant["name"],
                audio_data=b"mock_audio_data",
                timestamp=datetime.now()
            )

            # Simulate transcription
            intro_text = f"Hi, I'm {participant['name']}"
            await self._process_zoom_transcription(audio_data, intro_text)

    def _setup_zoom_audio_processing(self):
        """Set up audio processing from Zoom streams"""
        print("🎧 Setting up Zoom audio processing...")

        # Initialize audio processor for real-time transcription
        # This would integrate with AssemblyAI or similar service

        self.audio_processor = {
            "sample_rate": 16000,
            "channels": 1,
            "format": "pcm16"
        }

    async def _on_zoom_audio_received(self, participant_id: str, audio_data: bytes, participant_info: Dict):
        """Callback when audio is received from Zoom participant"""

        participant_name = participant_info.get("name", f"Participant_{participant_id}")

        print(f"🎤 Received audio from {participant_name} ({participant_id})")

        # Create audio data object
        zoom_audio = ZoomAudioData(
            participant_id=participant_id,
            participant_name=participant_name,
            audio_data=audio_data,
            timestamp=datetime.now()
        )

        # Process audio through transcription
        await self._process_zoom_audio(zoom_audio)

    async def _process_zoom_audio(self, audio_data: ZoomAudioData):
        """Process audio from Zoom through transcription service"""

        try:
            # Send audio to transcription service (AssemblyAI)
            transcription = await self._transcribe_audio(audio_data.audio_data)

            if transcription and transcription.strip():
                print(f"📝 Transcribed: '{transcription}' from {audio_data.participant_name}")

                # Process through meeting bot
                await self._process_zoom_transcription(audio_data, transcription)

        except Exception as e:
            print(f"❌ Error processing audio: {e}")

    async def _transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio using AssemblyAI or similar service"""

        # For now, return mock transcription
        # In real implementation, send to AssemblyAI
        return "Mock transcription from audio data"

    async def _process_zoom_transcription(self, audio_data: ZoomAudioData, transcription: str):
        """Process transcription through meeting bot logic"""

        # Create transcription event
        event = TranscriptionEvent(
            timestamp=audio_data.timestamp,
            speaker=audio_data.participant_name,
            text=transcription,
            confidence=0.9,
            is_final=True
        )

        bot_response = None

        # Handle introduction phase
        if self.meeting_bot.introduction_active:
            speaker_id = audio_data.participant_id
            introduction_processed = self.meeting_bot._process_introduction(transcription, speaker_id)

            if introduction_processed:
                if not self.meeting_bot.pending_participants:
                    bot_response = "Perfect! I've identified everyone. Let's begin the meeting."
                    self.meeting_bot.introduction_active = False
                    self.meeting_bot.facilitator_active = True
                else:
                    next_participant = self.meeting_bot.pending_participants[0]
                    bot_response = f"Great! {next_participant}, please introduce yourself."

        # Handle normal facilitation
        elif self.meeting_bot.facilitator_active:
            # Add to conversation history
            self.meeting_bot.conversation_history.append({
                "timestamp": audio_data.timestamp.isoformat(),
                "speaker": audio_data.participant_name,
                "content": transcription
            })

            # Check if bot should respond
            should_respond = self.meeting_bot._should_bot_respond_to_speaker(
                transcription, audio_data.participant_name
            )

            if should_respond:
                bot_response = self.meeting_bot._generate_facilitator_response_with_context(
                    transcription, audio_data.participant_name
                )

                # Add bot response to history
                if bot_response:
                    self.meeting_bot.conversation_history.append({
                        "timestamp": datetime.now().isoformat(),
                        "speaker": "facilitator_bot",
                        "content": bot_response
                    })

        # Send response back to Zoom
        if bot_response:
            await self._send_zoom_response(bot_response)

    async def _send_zoom_response(self, message: str):
        """Send bot response to Zoom meeting"""
        print(f"🤖 Bot response: {message}")

        # Send to Zoom chat
        if self.zoom_chat_callback:
            self.zoom_chat_callback(message)
        elif self.zoom_client:
            try:
                await self.zoom_client.send_chat_message(message)
            except Exception as e:
                print(f"⚠️ Could not send chat message: {e}")

    async def _send_introduction_message(self):
        """Send initial introduction message to Zoom meeting"""
        intro_message = (
            f"Hello everyone! I'm {self.meeting_bot.bot_name}, your AI meeting facilitator. "
            f"I'll help identify speakers and facilitate our discussion. "
            f"Please introduce yourselves one by one when I call on you."
        )

        await self._send_zoom_response(intro_message)

    def _on_participant_change(self, participant_info: Dict):
        """Handle participant joining/leaving"""
        action = participant_info.get("action")  # "joined" or "left"
        name = participant_info.get("name")

        print(f"👤 Participant {action}: {name}")

    def _on_chat_message_received(self, sender: str, message: str):
        """Handle chat messages from participants"""
        print(f"💬 Chat from {sender}: {message}")

        # Could process chat messages for commands
        if message.lower().startswith("@bot"):
            # Handle direct bot commands
            pass

    def _extract_meeting_id(self, meeting_url: str) -> str:
        """Extract meeting ID from Zoom URL"""
        import re
        match = re.search(r'/j/(\d+)', meeting_url)
        return match.group(1) if match else f"meeting_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    async def stop_analysis(self) -> Dict[str, any]:
        """Stop Zoom meeting analysis and return summary"""

        if not self.is_analyzing:
            return {"status": "error", "message": "No active analysis"}

        print("🛑 Stopping Zoom meeting analysis...")

        # Generate meeting summary
        summary = self._generate_meeting_summary()

        # Disconnect from Zoom
        if self.zoom_client:
            try:
                await self.zoom_client.leave_meeting()
            except Exception as e:
                print(f"⚠️ Error leaving Zoom meeting: {e}")

        # Clean up meeting bot
        result = self.meeting_bot.leave_meeting_with_voice()

        self.is_analyzing = False
        self.current_meeting_id = None

        return {
            "status": "success",
            "summary": summary,
            "meeting_data": result
        }

    def _generate_meeting_summary(self) -> Dict:
        """Generate comprehensive meeting summary"""
        return {
            "meeting_id": self.current_meeting_id,
            "duration": "N/A",  # Would calculate from start/end times
            "participants_identified": len(self.meeting_bot.participant_speakers),
            "total_messages": len(self.meeting_bot.conversation_history),
            "speaker_stats": self.meeting_bot.get_speaker_statistics(),
            "key_points": self._extract_key_points(),
            "action_items": self._extract_action_items(),
            "decisions": self._extract_decisions()
        }

    def _extract_key_points(self) -> List[str]:
        """Extract key discussion points"""
        key_points = []
        for entry in self.meeting_bot.conversation_history:
            if entry["speaker"] != "facilitator_bot" and len(entry["content"]) > 50:
                key_points.append(f"{entry['speaker']}: {entry['content']}")
        return key_points[:10]  # Top 10 key points

    def _extract_action_items(self) -> List[str]:
        """Extract action items from conversation"""
        action_items = []
        keywords = ["will do", "action", "todo", "follow up", "need to", "should", "must"]

        for entry in self.meeting_bot.conversation_history:
            if entry["speaker"] != "facilitator_bot":
                content_lower = entry["content"].lower()
                if any(keyword in content_lower for keyword in keywords):
                    action_items.append(f"{entry['speaker']}: {entry['content']}")

        return action_items

    def _extract_decisions(self) -> List[str]:
        """Extract decisions made during meeting"""
        decisions = []
        keywords = ["decided", "agreed", "conclusion", "final", "resolution", "we will"]

        for entry in self.meeting_bot.conversation_history:
            if entry["speaker"] != "facilitator_bot":
                content_lower = entry["content"].lower()
                if any(keyword in content_lower for keyword in keywords):
                    decisions.append(f"{entry['speaker']}: {entry['content']}")

        return decisions


# Example usage
async def main():
    """Example of using Zoom meeting analyzer"""

    analyzer = ZoomMeetingAnalyzer()

    # Get meeting details from environment variables
    meeting_id = os.getenv("MEETING_ID", "123456789")
    meeting_url = f"https://zoom.us/j/{meeting_id}"
    meeting_password = os.getenv("MEETING_PWD")
    participants_str = os.getenv("EXPECTED_PARTICIPANTS", "")
    expected_participants = [p.strip() for p in participants_str.split(",") if p.strip()]

    print(f"🔗 Connecting to meeting: {meeting_url}")
    print(f"👥 Expected participants: {expected_participants}")

    # Start analysis
    result = await analyzer.start_zoom_analysis(
        meeting_url=meeting_url,
        meeting_password=meeting_password,
        expected_participants=expected_participants
    )

    print(f"Analysis started: {result}")

    if result["status"] == "success":
        print("🎯 Bot is now facilitating the meeting...")
        print("   - Listening for participant introductions")
        print("   - Providing real-time facilitation")
        print("   - Press Ctrl+C to stop")

        try:
            # Keep running until interrupted
            while analyzer.is_analyzing:
                await asyncio.sleep(5)
        except KeyboardInterrupt:
            print("\n🛑 Stopping meeting analysis...")

        # Stop and get summary
        summary = await analyzer.stop_analysis()
        print(f"📊 Meeting summary: {summary}")
    else:
        print(f"❌ Failed to start analysis: {result['message']}")


if __name__ == "__main__":
    asyncio.run(main())
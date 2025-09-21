#!/usr/bin/env python3
"""
Test script for the voice-enabled meeting facilitator bot
"""
import asyncio
import sys
import os
import time

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from voice_meeting_bot import VoiceMeetingFacilitatorBot
from voice_handler import VoiceHandler




async def test_voice_bot():
    """Test voice-enabled bot functionality"""
    print("\n🤖 Testing Voice Meeting Bot")
    print("=" * 40)

    # Initialize voice bot
    bot = VoiceMeetingFacilitatorBot()

    print("\n1. Testing voice bot join...")
    result = await bot.join_meeting_with_voice(
        meeting_id="voice-test-123",
        notes_file_path="data/previous_meeting_notes.txt",
        meeting_topic="Voice Bot Test Meeting",
        participants=["Andri", "Omar", "Sid", "Seva"]
    )

    if result["status"] == "success":
        print("✅ Voice bot joined successfully")
        print(f"Meeting: {result['message']}")
        print("🎤 Bot is now listening for speech...")

        # Let the bot listen for a few seconds
        print("\n2. Testing speech interaction...")
        print("Try saying something like:")
        print("- 'Hello bot'")
        print("- 'What's on the agenda?'")
        print("- 'Let's move to the next item'")

        # Wait for interaction
        print("\nListening for 10 seconds...")
        await asyncio.sleep(10)

        # Test manual bot responses
        print("\n3. Testing agenda navigation...")
        bot.speak_agenda_item(0)
        await asyncio.sleep(2)

        print("\n4. Testing meeting summary...")
        bot.provide_meeting_summary()
        await asyncio.sleep(2)

        # Leave meeting
        print("\n5. Testing meeting leave...")
        leave_result = bot.leave_meeting_with_voice()
        if leave_result["status"] == "success":
            print("✅ Successfully left voice meeting")
            print(f"Message: {leave_result['message']}")
        else:
            print(f"❌ Failed to leave meeting: {leave_result['message']}")

    else:
        print(f"❌ Failed to join voice meeting: {result['message']}")




if __name__ == "__main__":
    print("Voice Meeting Bot Test Suite")

    if not os.getenv('OPENAI_API_KEY'):
        print("⚠️ OpenAI API key required for voice features")
        sys.exit(1)

    try:
        print("Running voice meeting bot test...")
        asyncio.run(test_voice_bot())

    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print("Make sure you have:")
        print("- OpenAI API key set")
        print("- Microphone permissions")
        print("- Audio libraries installed")
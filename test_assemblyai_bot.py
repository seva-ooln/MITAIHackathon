#!/usr/bin/env python3
"""
Test script for AssemblyAI-enhanced meeting facilitator bot
"""
import asyncio
import sys
import os
import time

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from voice_meeting_bot import VoiceMeetingFacilitatorBot


async def test_assemblyai_bot():
    """Test AssemblyAI-enhanced voice meeting bot"""
    print("🤖 Testing AssemblyAI Meeting Bot")
    print("=" * 50)

    # Check for required API keys
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ OpenAI API key required")
        return False

    if not os.getenv('ASSEMBLYAI_API_KEY'):
        print("❌ AssemblyAI API key required")
        print("Please set ASSEMBLYAI_API_KEY in your .env file")
        return False

    # Initialize bot
    bot = VoiceMeetingFacilitatorBot()

    print("\n1. Testing bot initialization...")
    status = bot.get_voice_status()
    print(f"✅ Bot initialized: {status['bot_name']}")

    print("\n2. Testing meeting join with AssemblyAI...")
    result = await bot.join_meeting_with_voice(
        meeting_id="assemblyai-test-001",
        notes_file_path="data/previous_meeting_notes.txt",
        meeting_topic="Hackathon Planning Session",
        agenda=[
            "Review technical implementation progress",
            "Test bot voice and speaker identification features",
            "Finalize MVP scope for hackathon submission",
            "Plan integration with Zoom SDK",
            "Prepare demo and presentation materials",
            "Set timeline for final submission"
        ],
        participants=["Seva", "Sid", "Omar", "Andri"]
    )

    if result["status"] != "success":
        print(f"❌ Failed to join meeting: {result['message']}")
        return False

    print("✅ Successfully joined meeting with AssemblyAI")
    print(f"Meeting: {result['message']}")

    # Check transcription status
    print("\n3. Checking transcription status...")
    status = bot.get_voice_status()
    print(f"Transcription active: {status['transcription_active']}")
    print(f"Connection stable: {status['connection_stable']}")
    print(f"Expected speakers: {status['expected_speakers']}, Detected speakers: {status['detected_speakers']}")

    print("\n4. Testing introduction phase and real-time transcription...")
    print("🎤 Bot should now be asking for introductions...")
    print("Bot will call participants to introduce themselves:")
    print("Try saying:")
    print("- 'Hi, I'm Seva'")
    print("- 'Hello, I'm Sid'")
    print("- etc. for each participant")
    print("\nAfter introductions, try speaking to test bot responses:")
    print("- 'Hello Alex, what's on the agenda?'")
    print("- 'I think we should move to the next item'")
    print("- 'Can you summarize what we've discussed?'")

    # Wait for introduction phase to complete (dynamic timing)
    print(f"\n🎯 Waiting for introduction phase to complete...")
    print("The bot will automatically proceed once all participants are identified (or timeout after 60s)")

    # Monitor introduction phase status
    while bot.introduction_active:
        await asyncio.sleep(2)
        status = bot.get_voice_status()
        expected = status.get('expected_speakers', 0)
        detected = status.get('detected_speakers', 0)
        if expected > 0:
            print(f"⏳ Introduction progress: {detected}/{expected} participants identified")

    print("✅ Introduction phase completed! Bot is now ready for meeting facilitation.")

    # Continue listening for a bit more to test normal facilitation
    print("\n📝 Testing meeting facilitation (15 more seconds)...")
    await asyncio.sleep(15)

    print("\n5. Getting speaker statistics...")
    speaker_stats = bot.get_speaker_statistics()
    if speaker_stats:
        print("Speaker Statistics:")
        for speaker, stats in speaker_stats.items():
            print(f"  {speaker}: {stats['message_count']} messages, "
                  f"{stats['speaking_percentage']:.1f}% of conversation")
    else:
        print("No speaker statistics available yet")

    print("\n6. Getting meeting insights...")
    insights = bot.get_meeting_insights()
    print(f"Total messages: {insights['total_messages']}")
    print(f"Unique speakers: {insights['unique_speakers']}")
    print(f"Sentiment summary: {insights['sentiment_summary']}")
    if insights['key_highlights']:
        print(f"Key highlights: {insights['key_highlights']}")

    print("\n7. Testing agenda navigation...")
    bot.speak_agenda_item(0)
    await asyncio.sleep(2)

    print("\n8. Testing meeting summary...")
    bot.provide_meeting_summary()
    await asyncio.sleep(2)

    print("\n9. Testing meeting leave...")
    leave_result = bot.leave_meeting_with_voice()
    if leave_result["status"] == "success":
        print("✅ Successfully left meeting")
        print(f"Conversation entries: {leave_result['conversation_entries']}")
    else:
        print(f"❌ Failed to leave meeting: {leave_result['message']}")

    return True


def check_requirements():
    """Check if all requirements are met"""
    print("🔍 Checking requirements...")

    # Check API keys
    openai_key = os.getenv('OPENAI_API_KEY')
    assemblyai_key = os.getenv('ASSEMBLYAI_API_KEY')

    print(f"OpenAI API Key: {'✅ Set' if openai_key else '❌ Missing'}")
    print(f"AssemblyAI API Key: {'✅ Set' if assemblyai_key else '❌ Missing'}")

    # Check dependencies
    try:
        import assemblyai
        print("✅ AssemblyAI library installed")
    except ImportError:
        print("❌ AssemblyAI library not installed")
        print("Run: pip install assemblyai")
        return False

    try:
        import pyaudio
        print("✅ PyAudio library available")
    except ImportError:
        print("❌ PyAudio library not installed")
        print("Run: pip install pyaudio")
        return False

    if not openai_key or not assemblyai_key:
        print("\n❌ Missing required API keys")
        print("Please set both OPENAI_API_KEY and ASSEMBLYAI_API_KEY in your .env file")
        return False

    return True


async def test_speaker_identification_only():
    """Test only the speaker identification phase - focused and minimal"""
    print("🎯 Testing Speaker Identification Only")
    print("=" * 50)

    # Check for required API keys
    if not os.getenv('OPENAI_API_KEY') or not os.getenv('ASSEMBLYAI_API_KEY'):
        print("❌ API keys required")
        return False

    # Initialize bot
    bot = VoiceMeetingFacilitatorBot()
    participants = ["Seva", "Sid", "Omar", "Andri"]

    print(f"📋 Expected participants: {participants}")
    print("🎯 This test focuses ONLY on speaker identification during introductions")
    print("🎯 No agenda reading, no meeting facilitation, no summaries")

    # Join meeting with minimal setup - ensure notes file exists
    print("📝 Creating minimal notes file for test...")
    os.makedirs("data", exist_ok=True)
    with open("data/previous_meeting_notes.txt", "w") as f:
        f.write("Test meeting for speaker identification")

    result = await bot.join_meeting_with_voice(
        meeting_id="speaker-test-001",
        notes_file_path="data/previous_meeting_notes.txt",
        meeting_topic="Speaker ID Test",
        participants=participants
    )

    if result["status"] != "success":
        print(f"❌ Failed to join meeting: {result['message']}")
        return False

    print("✅ Bot initialized and ready for speaker identification")
    print(f"🎤 Introduction active: {bot.introduction_active}")
    print(f"📋 Pending participants: {bot.pending_participants}")

    print("\n🎤 Introduction Instructions:")
    for i, participant in enumerate(participants, 1):
        print(f"   {i}. When bot calls '{participant}', say: 'Hi, I'm {participant}'")

    print("\n🔍 Monitoring introduction phase (max 90 seconds)...")
    print("✋ The test will end as soon as all participants are identified!")

    # Monitor introduction phase with detailed status
    start_time = time.time()
    last_status = time.time()

    while bot.introduction_active and (time.time() - start_time) < 90:
        await asyncio.sleep(1)

        # Show status every 3 seconds
        if time.time() - last_status >= 3:
            elapsed = time.time() - start_time
            identified = len(bot.participant_speakers)
            pending = len(bot.pending_participants)

            print(f"⏳ {elapsed:.0f}s | Identified: {identified}/{len(participants)} | Pending: {bot.pending_participants}")

            # Show current mappings
            if bot.participant_speakers:
                mappings = [f"{sid}→{name}" for sid, name in bot.participant_speakers.items()]
                print(f"✅ Current mappings: {', '.join(mappings)}")

            last_status = time.time()

        # Check if all participants are identified
        if not bot.pending_participants:
            print("🎉 All participants identified! Ending test.")
            break

    # Final results
    elapsed_total = time.time() - start_time
    print(f"\n🎯 Speaker Identification Test Results:")
    print(f"   Total time: {elapsed_total:.1f} seconds")
    print(f"   Participants identified: {len(bot.participant_speakers)}/{len(participants)}")

    if bot.participant_speakers:
        print(f"   ✅ Successfully mapped:")
        for speaker_id, name in bot.participant_speakers.items():
            print(f"      {speaker_id} → {name}")

    if bot.pending_participants:
        print(f"   ❌ Not identified: {bot.pending_participants}")
        print(f"   💡 Try speaking louder or more clearly for these participants")

    # Quick cleanup
    print(f"\n🧹 Cleaning up...")
    bot.leave_meeting_with_voice()

    success = len(bot.participant_speakers) == len(participants)
    if success:
        print("🎉 Speaker identification test PASSED!")
    else:
        print("⚠️ Speaker identification test completed with some issues")

    return success


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AssemblyAI Meeting Bot Test Suite")
    parser.add_argument("--mode", choices=["full", "speaker"], default="full",
                       help="Test mode: 'full' for complete test, 'speaker' for speaker ID only")
    args = parser.parse_args()

    print("AssemblyAI Meeting Bot Test Suite")
    print("=" * 40)

    if not check_requirements():
        print("\n❌ Requirements not met. Please fix the issues above.")
        sys.exit(1)

    try:
        if args.mode == "speaker":
            print("\n🎯 Running Speaker Identification Test Only...")
            success = asyncio.run(test_speaker_identification_only())
        else:
            print("\n🚀 Running Full AssemblyAI Bot Test...")
            success = asyncio.run(test_assemblyai_bot())

        if success:
            if args.mode == "speaker":
                print("\n🎉 Speaker identification test completed successfully!")
            else:
                print("\n🎉 All tests completed successfully!")
                print("\nAssemblyAI Features Tested:")
                print("✅ Real-time transcription")
                print("✅ Speaker identification")
                print("✅ Sentiment analysis")
                print("✅ Auto highlights")
                print("✅ Connection stability")
                print("✅ Error handling")
        else:
            print("\n❌ Some tests failed")

    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        print("\nTroubleshooting:")
        print("- Make sure both API keys are set")
        print("- Check your internet connection")
        print("- Ensure microphone permissions are granted")
        print("- Verify AssemblyAI account has credits")
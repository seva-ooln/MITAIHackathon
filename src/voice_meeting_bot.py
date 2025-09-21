import asyncio
import json
import time
import os
from typing import Dict, Optional, List
from datetime import datetime
from .context_manager import ContextManager, MeetingContext
from .ai_analyzer import AIAnalyzer
from .voice_handler import VoiceHandler
from .speech_transcriber import SpeechTranscriber, TranscriptionEvent


class VoiceMeetingFacilitatorBot:
    """Voice-enabled meeting facilitator bot with conversational capabilities"""

    def __init__(self):
        self.context_manager = ContextManager()
        self.ai_analyzer = AIAnalyzer()
        self.voice_handler = VoiceHandler()
        self.transcriber = SpeechTranscriber()

        self.current_meeting_context: Optional[MeetingContext] = None
        self.is_in_meeting = False
        self.conversation_history = []
        self.meeting_transcript = []

        # Bot personality settings
        self.bot_name = "Alex"
        self.facilitator_active = False

        # Speaker tracking
        self.participant_speakers = {}  # Map speaker IDs to participant names
        self.transcription_active = False

        # Introduction phase
        self.introduction_active = False
        self.pending_participants = []
        self.introduction_timeout = 60  # seconds - increased for better user experience

        # Load known speakers from previous meetings
        self.known_speakers = self._load_speaker_profiles()

    async def join_meeting_with_voice(self, meeting_id: str, notes_file_path: str = None,
                                    meeting_topic: str = "Team Meeting",
                                    agenda: list = None,
                                    participants: list = None) -> Dict[str, str]:
        """Join a meeting with voice capabilities enabled"""
        try:
            # Load or create meeting context
            self.current_meeting_context = self.context_manager.load_meeting_context(meeting_id)

            if not self.current_meeting_context:
                if not notes_file_path:
                    return {
                        "status": "error",
                        "message": "No meeting context found and no notes file provided. Please provide notes_file_path parameter."
                    }

                self.current_meeting_context = self.context_manager.create_context_from_notes_file(
                    meeting_id=meeting_id,
                    notes_file_path=notes_file_path,
                    meeting_topic=meeting_topic,
                    agenda=agenda,
                    participants=participants
                )

            # Generate and speak greeting
            greeting = self.ai_analyzer.generate_meeting_greeting(self.current_meeting_context)

            # Speak the greeting
            self.voice_handler.speak(greeting)

            # Get context analysis for facilitator insights
            analysis = self.ai_analyzer.analyze_meeting_context(self.current_meeting_context)

            self.is_in_meeting = True
            self.facilitator_active = True

            # Set up speaker mapping if participants provided
            if participants:
                self._setup_speaker_mapping(participants)

            # Start AssemblyAI transcription
            self._start_assemblyai_transcription()

            # Always start introduction phase for speaker mapping when there are participants
            if participants:
                self.pending_participants = participants.copy()
                need_introduction = self._check_known_speakers(participants)
                if need_introduction:
                    self._start_introduction_phase(self.pending_participants)
                else:
                    self.facilitator_active = True
            else:
                # No participants specified, start with normal facilitation
                self.facilitator_active = True

            # Note: We're now using AssemblyAI instead of basic speech recognition

            return {
                "status": "success",
                "meeting_id": meeting_id,
                "greeting": greeting,
                "context_analysis": analysis.get("analysis", ""),
                "message": f"Voice bot joined meeting: {self.current_meeting_context.meeting_topic}",
                "voice_enabled": True
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to join meeting with voice: {str(e)}"
            }

    def _setup_speaker_mapping(self, participants: List[str]):
        """Set up initial speaker mapping for participants"""
        # Create mapping from generic speaker labels to participant names
        speaker_mapping = {}
        for i, participant in enumerate(participants):
            speaker_key = f"Speaker {i + 1}"
            speaker_mapping[speaker_key] = participant

        self.transcriber.set_speaker_names(speaker_mapping)
        print(f"🎯 Set up speaker mapping for {len(participants)} participants")

    def _start_assemblyai_transcription(self):
        """Start AssemblyAI real-time transcription"""
        try:
            self.transcriber.start_transcription(
                transcription_callback=self._handle_assemblyai_transcription,
                error_callback=self._handle_assemblyai_error
            )
            self.transcription_active = True
            print("🎤 AssemblyAI transcription started")

        except Exception as e:
            print(f"❌ Failed to start AssemblyAI transcription: {e}")

    def _handle_assemblyai_transcription(self, event: TranscriptionEvent):
        """Handle transcription events from AssemblyAI"""
        if not self.is_in_meeting:
            return

        # Only process final transcripts for bot responses
        if not event.is_final:
            return

        # Get speaker info
        speaker_id = event.speaker or "Unknown"
        speaker_name = self.transcriber.speaker_mapping.get(speaker_id, speaker_id)

        print(f"🎤 {speaker_name} ({speaker_id}): {event.text}")

        # Handle introduction phase
        if self.introduction_active:
            introduction_processed = self._process_introduction(event.text, speaker_id)
            if introduction_processed:
                return  # Introduction was processed, don't continue with normal flow

        # Only proceed with normal facilitation if bot is active
        if not self.facilitator_active:
            return

        # Add to conversation history with enhanced information
        conversation_entry = {
            "timestamp": event.timestamp.isoformat(),
            "speaker": speaker_name,
            "speaker_id": speaker_id,
            "content": event.text,
            "confidence": event.confidence,
            "sentiment": event.sentiment,
            "highlights": event.highlights
        }

        self.conversation_history.append(conversation_entry)

        # Check if bot should respond (similar logic but with speaker info)
        should_respond = self._should_bot_respond_to_speaker(event.text, speaker_name)

        if should_respond:
            response = self._generate_facilitator_response_with_context(event.text, speaker_name)
            if response:
                # Add bot response to history
                self.conversation_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "speaker": "facilitator_bot",
                    "speaker_id": "bot",
                    "content": response,
                    "confidence": 1.0,
                    "sentiment": "neutral"
                })

                # Speak the response
                self.voice_handler.speak(response)

    def _handle_assemblyai_error(self, error_message: str):
        """Handle AssemblyAI transcription errors"""
        print(f"❌ AssemblyAI Error: {error_message}")

        # Attempt to restart transcription if connection failed
        if "connection" in error_message.lower() and self.transcription_active:
            print("🔄 Attempting to restart transcription...")
            self._restart_transcription()

    def _restart_transcription(self):
        """Restart AssemblyAI transcription after error"""
        try:
            self.transcriber.stop_transcription()
            time.sleep(2)
            self._start_assemblyai_transcription()
        except Exception as e:
            print(f"❌ Failed to restart transcription: {e}")

    def _start_introduction_phase(self, participants: List[str]):
        """Start introduction phase for speaker identification"""
        self.introduction_active = True
        self.pending_participants = participants.copy()
        self.facilitator_active = False  # Disable normal facilitation during introduction

        # Wait a moment for transcription to start, then begin introductions
        asyncio.create_task(self._run_introduction_phase())

    async def _run_introduction_phase(self):
        """Run the introduction phase"""
        print(f"🎯 Starting introduction phase for {len(self.pending_participants)} participants")
        await asyncio.sleep(2)  # Wait for transcription to stabilize

        if not self.pending_participants:
            print("⚠️ No pending participants, ending introduction phase")
            self._end_introduction_phase()
            return

        first_participant = self.pending_participants[0]
        intro_message = (
            f"Hello everyone! I'm {self.bot_name}, your meeting facilitator. "
            f"To help me identify speakers, please introduce yourselves one by one. "
            f"Simply say 'Hi, I'm [your name]' when I call on you. "
            f"Let's start with {first_participant}."
        )

        self.voice_handler.speak(intro_message)
        print(f"🗣️ Bot asked for introductions, waiting for {len(self.pending_participants)} participants")

        # Monitor for introductions - only end when all participants are identified or timeout
        start_time = time.time()
        check_count = 0
        while self.introduction_active and self.pending_participants:
            await asyncio.sleep(1)
            check_count += 1

            # Print status every 5 seconds
            if check_count % 5 == 0:
                elapsed = time.time() - start_time
                remaining_participants = len(self.pending_participants)
                print(f"⏳ Introduction phase active: {elapsed:.0f}s elapsed, {remaining_participants} participants remaining: {self.pending_participants}")

            # Check if we've exceeded the timeout
            if time.time() - start_time > self.introduction_timeout:
                print(f"⏰ Introduction phase timeout after {self.introduction_timeout} seconds")
                break

        print(f"🏁 Introduction phase ending. Active: {self.introduction_active}, Pending: {self.pending_participants}")
        if self.introduction_active:
            self._end_introduction_phase()

    def _process_introduction(self, transcript: str, speaker_id: str):
        """Process speech during introduction phase"""
        transcript_lower = transcript.lower().strip()

        print(f"🔍 Processing introduction: '{transcript}' from speaker {speaker_id}")
        print(f"📋 Pending participants: {self.pending_participants}")

        # Look for introduction patterns
        for participant in self.pending_participants[:]:
            participant_lower = participant.lower()

            # Check if participant introduces themselves
            intro_patterns = [
                f"hi i'm {participant_lower}",
                f"hello i'm {participant_lower}",
                f"i'm {participant_lower}",
                f"this is {participant_lower}",
                f"my name is {participant_lower}",
                f"i am {participant_lower}",
                participant_lower
            ]

            # Check for matches
            matched = False
            for pattern in intro_patterns:
                if pattern in transcript_lower:
                    matched = True
                    break

            if matched:
                # Map this speaker ID to the participant
                self.transcriber.speaker_mapping[speaker_id] = participant
                self.participant_speakers[speaker_id] = participant
                self.pending_participants.remove(participant)

                print(f"✅ Identified {speaker_id} as {participant}")

                # Acknowledge and move to next person
                if self.pending_participants:
                    next_participant = self.pending_participants[0]
                    response = f"Great, thanks {participant}! {next_participant}, please introduce yourself."
                    self.voice_handler.speak(response)
                else:
                    # All participants identified
                    response = f"Perfect, thanks {participant}! I've identified everyone."
                    self.voice_handler.speak(response)
                    self._end_introduction_phase()
                return True

        # If no match found, provide encouragement
        if transcript_lower and len(transcript_lower) > 5:  # Ignore very short utterances
            print(f"❓ Could not identify speaker from: '{transcript}'")

        return False

    def _end_introduction_phase(self):
        """End the introduction phase"""
        print(f"🎯 Ending introduction phase. Identified: {len(self.participant_speakers)}, Pending: {len(self.pending_participants)}")

        self.introduction_active = False

        if self.pending_participants:
            # Some participants didn't introduce themselves
            remaining = ", ".join(self.pending_participants)
            message = f"I'll continue with the meeting. I wasn't able to identify: {remaining}. You can say 'I'm [name]' at any time to help me identify you."
        else:
            message = "Perfect! I've identified everyone. Let's begin the meeting."

        self.voice_handler.speak(message)
        self.facilitator_active = True  # Now allow normal facilitation

        print(f"✅ Introduction phase complete. Identified speakers: {self.participant_speakers}")
        print(f"🎤 Facilitator now active, ready to respond to meeting conversation")

        # Save speaker profiles for future meetings
        self._save_speaker_profiles()

    def _load_speaker_profiles(self) -> Dict[str, Dict]:
        """Load participant meeting history from previous sessions"""
        # Try new filename first, fall back to old filename for compatibility
        new_file = os.path.join(self.context_manager.context_dir, "participant_history.json")
        old_file = os.path.join(self.context_manager.context_dir, "speaker_profiles.json")

        for file_path in [new_file, old_file]:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Clean up any old speaker_id mappings from legacy data
                        for participant_data in data.values():
                            participant_data.pop("last_speaker_id", None)
                        return data
                except Exception as e:
                    print(f"⚠️ Could not load participant history from {file_path}: {e}")

        return {}

    def _save_speaker_profiles(self):
        """Save participant meeting history (NOT speaker IDs which are session-specific)"""
        if not self.participant_speakers:
            return

        speaker_file = os.path.join(self.context_manager.context_dir, "participant_history.json")

        # Update participant history (remove unreliable speaker_id mapping)
        for speaker_id, participant_name in self.participant_speakers.items():
            if participant_name not in self.known_speakers:
                self.known_speakers[participant_name] = {
                    "meetings_attended": [],
                    "total_meetings": 0,
                    "first_meeting": datetime.now().isoformat()
                }

            # Update meeting history only (no speaker ID mapping)
            self.known_speakers[participant_name]["total_meetings"] += 1

            if self.current_meeting_context:
                meeting_info = {
                    "meeting_id": self.current_meeting_context.meeting_id,
                    "date": datetime.now().isoformat(),
                    "topic": self.current_meeting_context.meeting_topic
                }
                self.known_speakers[participant_name]["meetings_attended"].append(meeting_info)

        try:
            with open(speaker_file, 'w', encoding='utf-8') as f:
                json.dump(self.known_speakers, f, indent=2, ensure_ascii=False)
            print(f"💾 Saved meeting history for {len(self.participant_speakers)} participants")
        except Exception as e:
            print(f"⚠️ Could not save participant history: {e}")

    def _check_known_speakers(self, participants: List[str]) -> bool:
        """Always require fresh introductions since AssemblyAI speaker IDs are session-specific"""
        print("🔄 Speaker identification required: AssemblyAI assigns new speaker IDs each session")

        # Always need introduction for all participants
        # AssemblyAI speaker IDs (speaker_A, speaker_B, etc.) are session-specific
        # and cannot be reliably mapped across different sessions
        self.pending_participants = participants.copy()

        # Check if we've met these participants before (for greeting purposes only)
        known_names = [name for name in participants if name in self.known_speakers]
        new_names = [name for name in participants if name not in self.known_speakers]

        if known_names and new_names:
            print(f"👋 Familiar participants: {', '.join(known_names)}")
            print(f"🆕 New participants: {', '.join(new_names)}")
        elif known_names:
            print(f"👋 All participants have attended previous meetings")
        else:
            print(f"🆕 All participants are new")

        # Always return True to require introductions
        return True

    def _should_bot_respond_to_speaker(self, transcript: str, speaker_name: str) -> bool:
        """Enhanced logic to determine if bot should respond (includes speaker info)"""
        transcript_lower = transcript.lower()

        # Don't respond to own speech
        if speaker_name == "facilitator_bot":
            return False

        # Direct address to bot
        if any(name in transcript_lower for name in [self.bot_name.lower(), "bot", "facilitator", "alex"]):
            return True

        # Questions
        if any(word in transcript_lower for word in ["what", "how", "when", "where", "who", "why", "?"]):
            return True

        # Facilitation keywords
        if any(word in transcript_lower for word in ["stuck", "blocked", "help", "next steps", "action", "decision", "agenda"]):
            return True

        # Meeting flow keywords
        if any(phrase in transcript_lower for phrase in ["move on", "next item", "wrap up", "summarize", "time check"]):
            return True

        # If there's a long pause in conversation (no recent speech)
        if len(self.conversation_history) > 0:
            last_entry = self.conversation_history[-1]
            last_time = datetime.fromisoformat(last_entry["timestamp"])
            if (datetime.now() - last_time).seconds > 15:  # 15 second silence
                return True

        return False

    def _generate_facilitator_response_with_context(self, transcript: str, speaker_name: str) -> Optional[str]:
        """Generate facilitator response with speaker context"""
        # Get recent conversation with speaker information
        recent_conversation = []
        for entry in self.conversation_history[-5:]:
            speaker = entry.get("speaker", "Unknown")
            content = entry.get("content", "")
            recent_conversation.append(f"{speaker}: {content}")

        recent_context = "\n".join(recent_conversation)

        prompt = f"""
        You are {self.bot_name}, a meeting facilitator bot. {speaker_name} just said: "{transcript}"

        Recent conversation:
        {recent_context}

        Meeting topic: {self.current_meeting_context.meeting_topic if self.current_meeting_context else "General"}

        Participants: {', '.join(self.current_meeting_context.participants) if self.current_meeting_context else 'Unknown'}

        Provide a brief, helpful facilitator response (1-2 sentences max). Be:
        - Conversational and natural
        - Helpful in moving discussion forward
        - Aware of who is speaking (you can address {speaker_name} by name)
        - Focused on the meeting agenda
        - Encouraging and positive

        If it's a direct question to you, answer it. Otherwise, provide gentle facilitation.
        """

        try:
            response = self.ai_analyzer.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"You are {self.bot_name}, a friendly and efficient meeting facilitator who knows participant names."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.7
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            # Fallback responses with speaker awareness
            fallback_responses = [
                f"Thanks for that input, {speaker_name}. What does everyone else think?",
                f"Great point, {speaker_name}. Let's keep moving forward. What's our next step?",
                f"Good discussion. Should we capture that as an action item?",
                f"Thanks for sharing, {speaker_name}. How can we build on that idea?"
            ]
            return fallback_responses[len(self.conversation_history) % len(fallback_responses)]

    def _handle_participant_speech(self, transcript: str):
        """Handle speech from meeting participants"""
        if not self.facilitator_active or not self.is_in_meeting:
            return

        # Add to conversation history
        self.conversation_history.append({
            "timestamp": datetime.now().isoformat(),
            "speaker": "participant",
            "content": transcript
        })

        # Check if bot should respond
        should_respond = self._should_bot_respond(transcript)

        if should_respond:
            response = self._generate_facilitator_response(transcript)
            if response:
                # Add bot response to history
                self.conversation_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "speaker": "facilitator_bot",
                    "content": response
                })

                # Speak the response
                self.voice_handler.speak(response)

    def _should_bot_respond(self, transcript: str) -> bool:
        """Determine if bot should respond to participant speech"""
        # Bot responds if:
        # 1. Directly addressed (mentioned by name)
        # 2. Question is asked
        # 3. Discussion seems stuck/needs facilitation
        # 4. Action items are mentioned

        transcript_lower = transcript.lower()

        # Direct address
        if any(name in transcript_lower for name in [self.bot_name.lower(), "bot", "facilitator"]):
            return True

        # Questions
        if any(word in transcript_lower for word in ["what", "how", "when", "where", "who", "why", "?"]):
            return True

        # Facilitation keywords
        if any(word in transcript_lower for word in ["stuck", "blocked", "help", "next steps", "action", "decision"]):
            return True

        # Silence detection (if no speech for a while, offer to help)
        if len(self.conversation_history) > 0:
            last_speech_time = datetime.fromisoformat(self.conversation_history[-1]["timestamp"])
            if (datetime.now() - last_speech_time).seconds > 30:
                return True

        return False

    def _generate_facilitator_response(self, transcript: str) -> Optional[str]:
        """Generate appropriate facilitator response"""
        recent_conversation = " ".join([
            entry["content"] for entry in self.conversation_history[-5:]
        ])

        prompt = f"""
        You are {self.bot_name}, a meeting facilitator bot. A participant just said: "{transcript}"

        Recent conversation context: {recent_conversation}

        Meeting topic: {self.current_meeting_context.meeting_topic if self.current_meeting_context else "General"}

        Provide a brief, helpful facilitator response (1-2 sentences max). Be:
        - Conversational and natural
        - Helpful in moving discussion forward
        - Focused on the meeting agenda
        - Encouraging and positive

        If it's a direct question to you, answer it. Otherwise, provide gentle facilitation.
        """

        try:
            response = self.ai_analyzer.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"You are {self.bot_name}, a friendly and efficient meeting facilitator."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.7
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            # Fallback responses
            fallback_responses = [
                "That's a great point. What does everyone else think?",
                "Let's keep moving forward. What's our next step?",
                "Good discussion. Should we capture that as an action item?",
                "Thanks for sharing. How can we build on that idea?"
            ]
            return fallback_responses[len(self.conversation_history) % len(fallback_responses)]

    def speak_agenda_item(self, item_index: int):
        """Speak a specific agenda item"""
        if not self.current_meeting_context or item_index >= len(self.current_meeting_context.agenda):
            self.voice_handler.speak("Sorry, that agenda item doesn't exist.")
            return

        agenda_item = self.current_meeting_context.agenda[item_index]
        message = f"Let's move to agenda item {item_index + 1}: {agenda_item}"
        self.voice_handler.speak(message)

    def provide_meeting_summary(self):
        """Provide voice summary of the meeting"""
        if not self.conversation_history:
            self.voice_handler.speak("We haven't had much discussion yet. Let's keep the conversation going!")
            return

        # Generate summary from conversation
        conversation_text = " ".join([entry["content"] for entry in self.conversation_history])

        summary_prompt = f"""
        Summarize this meeting discussion in 2-3 sentences for the participants:
        {conversation_text}

        Focus on key decisions, action items, and next steps.
        """

        try:
            response = self.ai_analyzer.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a meeting facilitator providing a brief, clear summary."},
                    {"role": "user", "content": summary_prompt}
                ],
                max_tokens=150,
                temperature=0.6
            )

            summary = response.choices[0].message.content.strip()
            self.voice_handler.speak(f"Here's what we've covered so far: {summary}")

        except Exception:
            self.voice_handler.speak("We've had a productive discussion. Let's continue moving through our agenda.")

    def mute_bot(self):
        """Temporarily mute the bot"""
        self.facilitator_active = False
        print("🔇 Bot muted - will not respond to speech")

    def unmute_bot(self):
        """Unmute the bot"""
        self.facilitator_active = True
        self.voice_handler.speak("I'm back and ready to help facilitate!")

    def leave_meeting_with_voice(self) -> Dict[str, str]:
        """Leave meeting and provide voice summary"""
        if not self.is_in_meeting:
            return {"status": "error", "message": "Not in an active meeting"}

        # Stop AssemblyAI transcription
        if self.transcription_active:
            self.transcriber.stop_transcription()
            self.transcription_active = False

        # Stop basic voice handler (if still running)
        if self.voice_handler.is_listening():
            self.voice_handler.stop_listening()

        # Generate final summary
        if self.conversation_history:
            conversation_text = " ".join([entry["content"] for entry in self.conversation_history])
            next_steps = self.ai_analyzer.suggest_next_steps(
                self.current_meeting_context,
                conversation_text
            )

            # Speak farewell and next steps
            farewell = f"Thanks everyone for a productive meeting! {next_steps}"
            self.voice_handler.speak(farewell)
        else:
            self.voice_handler.speak("Thanks for including me in your meeting. Have a great day!")

        # Reset state
        meeting_topic = self.current_meeting_context.meeting_topic if self.current_meeting_context else "Unknown"
        self.current_meeting_context = None
        self.is_in_meeting = False
        self.facilitator_active = False
        conversation_count = len(self.conversation_history)
        self.conversation_history = []

        return {
            "status": "success",
            "message": f"Left voice meeting: {meeting_topic}",
            "conversation_entries": conversation_count
        }

    def get_meeting_context_summary(self) -> str:
        """Get formatted summary of current meeting context"""
        if not self.current_meeting_context:
            return "No active meeting context"

        return self.context_manager.get_context_summary(self.current_meeting_context)

    def get_speaker_statistics(self) -> Dict[str, Dict]:
        """Get detailed speaker statistics from AssemblyAI"""
        return self.transcriber.get_speaker_statistics()

    def get_meeting_insights(self) -> Dict[str, any]:
        """Get meeting insights including sentiment and highlights"""
        insights = {
            "total_messages": len(self.conversation_history),
            "unique_speakers": len(set(entry.get("speaker", "Unknown") for entry in self.conversation_history)),
            "sentiment_summary": {},
            "key_highlights": [],
            "transcription_stats": self.transcriber.get_transcription_statistics()
        }

        # Analyze sentiment distribution
        sentiments = [entry.get("sentiment") for entry in self.conversation_history if entry.get("sentiment")]
        for sentiment in sentiments:
            insights["sentiment_summary"][sentiment] = insights["sentiment_summary"].get(sentiment, 0) + 1

        # Collect highlights
        for entry in self.conversation_history:
            if entry.get("highlights"):
                insights["key_highlights"].extend(entry["highlights"])

        return insights

    def get_voice_status(self) -> Dict[str, any]:
        """Get current voice bot status"""
        return {
            "is_in_meeting": self.is_in_meeting,
            "voice_enabled": True,
            "transcription_active": self.transcription_active,
            "connection_stable": self.transcriber.connection_stable,
            "facilitator_active": self.facilitator_active,
            "current_meeting": self.current_meeting_context.meeting_topic if self.current_meeting_context else None,
            "conversation_entries": len(self.conversation_history),
            "bot_name": self.bot_name,
            "speaker_count": len(self.transcriber.speakers),
            "expected_speakers": len(self.transcriber.speaker_mapping),
            "detected_speakers": len(self.transcriber.speakers)
        }
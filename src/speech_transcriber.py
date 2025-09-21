import os
import asyncio
import json
import threading
import time
import numpy as np
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime
import pyaudio
import assemblyai as aai
from assemblyai.streaming.v3 import (
    BeginEvent,
    StreamingClient,
    StreamingClientOptions,
    StreamingError,
    StreamingEvents,
    StreamingParameters,
    StreamingSessionParameters,
    TerminationEvent,
    TurnEvent,
)
from dotenv import load_dotenv

load_dotenv()


@dataclass
class TranscriptionEvent:
    """Data class for transcription events"""
    timestamp: datetime
    speaker: Optional[str]
    text: str
    confidence: float
    is_final: bool
    sentiment: Optional[str] = None
    highlights: Optional[List[str]] = None
    words: Optional[List[Dict]] = None


@dataclass
class SpeakerInfo:
    """Information about a detected speaker"""
    speaker_id: str
    speaker_label: str
    total_speaking_time: float
    message_count: int
    last_spoken: datetime


class SpeechTranscriber:
    """Real-time transcription with speaker identification using AssemblyAI"""

    def __init__(self, input_device_index=None):
        # Set up AssemblyAI API key
        self.api_key = os.getenv('ASSEMBLYAI_API_KEY')

        # Audio configuration
        self.sample_rate = 16000
        self.chunk_size = 1024
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.input_device_index = input_device_index  # Allow manual device selection

        # Audio processing settings for low volume
        self.audio_amplification = 20.0  # Amplify audio by 20x
        self.noise_threshold = 30  # Minimum level to consider as speech (lower for quiet mics)
        self.enable_audio_boost = True

        # PyAudio setup
        self.audio = pyaudio.PyAudio()
        self.stream = None

        # Transcription state
        self.client = None
        self.is_transcribing = False
        self.connection_stable = False

        # Callbacks
        self.transcription_callback: Optional[Callable[[TranscriptionEvent], None]] = None
        self.error_callback: Optional[Callable[[str], None]] = None

        # Speaker tracking
        self.speakers: Dict[str, SpeakerInfo] = {}
        self.speaker_mapping: Dict[str, str] = {}  # Map speaker_label to custom names

        # Connection management
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 2.0
        self.last_heartbeat = None

        # Statistics
        self.total_transcribed_duration = 0.0
        self.total_words_transcribed = 0
        self.start_time = None

    def configure_realtime_transcription(self):
        """Configure AssemblyAI streaming client with Universal model"""
        try:
            # Create StreamingClient with Universal streaming model
            client = StreamingClient(
                StreamingClientOptions(
                    api_key=self.api_key,
                    api_host="streaming.assemblyai.com"
                )
            )
            return client
        except Exception as e:
            print(f"❌ Error creating StreamingClient: {e}")
            return None

    def _on_begin(self, client, event: BeginEvent):
        """Handle session begin"""
        self.connection_stable = True
        self.last_heartbeat = datetime.now()
        print(f"🔗 AssemblyAI session started: {event.id}")
        print(f"✅ Ready to receive audio and transcribe with speaker identification")

    def _on_turn(self, client, event: TurnEvent):
        """Handle turn events (this is where transcripts come in)"""
        try:
            print(f"📥 Received turn: '{event.transcript}' (end_of_turn: {event.end_of_turn})")

            if event.transcript and len(event.transcript.strip()) > 0:
                print(f"🎤 Processing transcript: '{event.transcript}'")

                # Create our TranscriptionEvent from the TurnEvent
                transcription_event = TranscriptionEvent(
                    timestamp=datetime.now(),
                    speaker=getattr(event, 'speaker', 'Unknown'),  # Get speaker if available
                    text=event.transcript,
                    confidence=getattr(event, 'confidence', 0.9),
                    is_final=event.end_of_turn,
                    sentiment=None,
                    highlights=None,
                    words=None
                )

                # Update speaker tracking
                speaker_id = getattr(event, 'speaker', 'Unknown')
                self._update_speaker_info(speaker_id, event.transcript, len(event.transcript.split()))

                # Call our callback with the converted event
                if self.transcription_callback:
                    self.transcription_callback(transcription_event)

                # Update heartbeat
                self.last_heartbeat = datetime.now()

                # Enable turn formatting if not already enabled
                if event.end_of_turn and not getattr(event, 'turn_is_formatted', True):
                    print("🔄 Enabling turn formatting...")
                    params = StreamingSessionParameters(format_turns=True)
                    client.set_params(params)

        except Exception as e:
            print(f"❌ Error processing turn: {e}")

    def _on_terminated(self, client, event: TerminationEvent):
        """Handle session termination"""
        self.connection_stable = False
        print(f"🔗 AssemblyAI session terminated: {event.audio_duration_seconds} seconds processed")

    def _on_error_event(self, client, error: StreamingError):
        """Handle streaming errors"""
        error_msg = f"AssemblyAI Streaming Error: {error}"
        print(f"❌ {error_msg}")

        if self.error_callback:
            self.error_callback(error_msg)

    def _start_microphone_stream(self):
        """Start the microphone stream in a separate thread"""
        try:
            print("🎤 Starting MicrophoneStream...")
            self.client.stream(
                aai.extras.MicrophoneStream(sample_rate=16000)
            )
        except Exception as e:
            print(f"❌ MicrophoneStream error: {e}")
            if self.error_callback:
                self.error_callback(f"MicrophoneStream error: {e}")

    def _process_transcript(self, transcript):
        """Process transcription results from Universal Streaming"""
        if not transcript.text or len(transcript.text.strip()) == 0:
            return

        # Update statistics
        self.total_words_transcribed += len(transcript.text.split())

        # Extract speaker information from Universal Streaming with speaker diarization
        speaker_id = getattr(transcript, 'speaker', getattr(transcript, 'speaker_label', 'Unknown'))
        speaker_label = self._get_speaker_label(speaker_id)

        # Update speaker tracking
        self._update_speaker_info(speaker_id, transcript.text, len(transcript.text.split()))

        # Extract confidence (may be available)
        confidence = getattr(transcript, 'confidence', 0.9)

        # Extract additional features
        sentiment = getattr(transcript, 'sentiment', None)
        highlights = getattr(transcript, 'highlights', None)
        words = getattr(transcript, 'words', None)

        # Create transcription event
        event = TranscriptionEvent(
            timestamp=datetime.now(),
            speaker=speaker_label,
            text=transcript.text,
            confidence=confidence,
            is_final=True,
            sentiment=sentiment,
            highlights=highlights,
            words=words
        )

        # Call callback
        if self.transcription_callback:
            self.transcription_callback(event)

        # Update heartbeat
        self.last_heartbeat = datetime.now()


    def _get_speaker_label(self, speaker_id: str) -> str:
        """Get human-readable speaker label"""
        if speaker_id in self.speaker_mapping:
            return self.speaker_mapping[speaker_id]

        # Auto-assign speaker labels
        speaker_count = len(self.speakers)
        if speaker_id not in self.speakers:
            default_label = f"Speaker {speaker_count + 1}"
            self.speaker_mapping[speaker_id] = default_label
            return default_label

        return speaker_id

    def _update_speaker_info(self, speaker_id: str, text: str, word_count: int):
        """Update speaker statistics"""
        now = datetime.now()

        if speaker_id not in self.speakers:
            self.speakers[speaker_id] = SpeakerInfo(
                speaker_id=speaker_id,
                speaker_label=self._get_speaker_label(speaker_id),
                total_speaking_time=0.0,
                message_count=0,
                last_spoken=now
            )

        speaker = self.speakers[speaker_id]
        speaker.message_count += 1
        speaker.last_spoken = now

        # Estimate speaking time (rough calculation)
        estimated_duration = word_count * 0.5  # ~0.5 seconds per word
        speaker.total_speaking_time += estimated_duration

    def set_speaker_names(self, speaker_mapping: Dict[str, str]):
        """Map speaker IDs to custom names"""
        self.speaker_mapping.update(speaker_mapping)

    def start_transcription(self,
                          transcription_callback: Callable[[TranscriptionEvent], None],
                          error_callback: Optional[Callable[[str], None]] = None):
        """Start real-time transcription using AssemblyAI MicrophoneStream (working approach)"""
        self.transcription_callback = transcription_callback
        self.error_callback = error_callback

        try:
            # Check if AssemblyAI API key is set
            if not self.api_key:
                raise Exception("ASSEMBLYAI_API_KEY not found in environment variables")

            print("🎤 Using AssemblyAI MicrophoneStream for reliable audio capture")

            # Create streaming client using the working approach
            self.client = StreamingClient(
                StreamingClientOptions(
                    api_key=self.api_key,
                    api_host="streaming.assemblyai.com",
                )
            )

            # Set up event handlers using the working pattern
            self.client.on(StreamingEvents.Begin, self._on_begin)
            self.client.on(StreamingEvents.Turn, self._on_turn)
            self.client.on(StreamingEvents.Termination, self._on_terminated)
            self.client.on(StreamingEvents.Error, self._on_error_event)

            print("🔗 Connecting to AssemblyAI streaming service...")

            # Connect with speaker diarization enabled
            self.client.connect(
                StreamingParameters(
                    sample_rate=16000,
                    format_turns=True,
                    speaker_labels=True,  # Enable speaker diarization
                    end_of_turn_confidence_threshold=0.7,
                    min_end_of_turn_silence_when_confident=160,
                    max_turn_silence=2400,
                    keyterms_prompt=[]
                )
            )

            self.is_transcribing = True
            self.connection_stable = True
            self.start_time = datetime.now()

            # Start streaming in a background thread using MicrophoneStream
            self.streaming_thread = threading.Thread(target=self._start_microphone_stream, daemon=True)
            self.streaming_thread.start()

            print("🎤 AssemblyAI transcription started with MicrophoneStream")

        except Exception as e:
            error_msg = f"Failed to start transcription: {str(e)}"
            print(f"❌ {error_msg}")
            if self.error_callback:
                self.error_callback(error_msg)

    def _amplify_audio(self, audio_data):
        """Amplify audio data for low volume microphones"""
        if not self.enable_audio_boost:
            return audio_data

        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)

            # Calculate current volume
            volume = np.sqrt(np.mean(audio_array**2))

            # Only amplify if volume is above noise threshold
            if volume > self.noise_threshold:
                # Amplify audio
                amplified = audio_array.astype(np.float32) * self.audio_amplification

                # Prevent clipping by normalizing if needed
                max_val = np.max(np.abs(amplified))
                if max_val > 32767:  # int16 max value
                    amplified = amplified * (32767 / max_val)

                # Convert back to int16
                amplified = amplified.astype(np.int16)
                return amplified.tobytes()
            else:
                return audio_data

        except Exception as e:
            print(f"⚠️ Audio amplification error: {e}")
            return audio_data

    def _stream_audio(self):
        """Stream audio data to AssemblyAI Universal Streaming"""
        audio_chunks_sent = 0
        last_volume_check = time.time()

        while self.is_transcribing and self.stream:
            try:
                audio_data = self.stream.read(self.chunk_size, exception_on_overflow=False)

                # Check audio levels every 3 seconds
                current_time = time.time()
                if current_time - last_volume_check > 3:
                    try:
                        # Convert bytes to numpy array for volume analysis
                        audio_array = np.frombuffer(audio_data, dtype=np.int16)
                        original_volume = np.sqrt(np.mean(audio_array**2))

                        # Show original and amplified volume
                        if self.enable_audio_boost and original_volume > self.noise_threshold:
                            amplified_data = self._amplify_audio(audio_data)
                            amplified_array = np.frombuffer(amplified_data, dtype=np.int16)
                            amplified_volume = np.sqrt(np.mean(amplified_array**2))
                            print(f"🔊 Audio: {original_volume:.0f} → {amplified_volume:.0f} (amplified)")
                        else:
                            print(f"🔊 Audio level: {original_volume:.0f} (below threshold: {self.noise_threshold})")

                        last_volume_check = current_time
                    except Exception as vol_error:
                        print(f"⚠️ Volume check error: {vol_error}")

                if self.client and self.connection_stable:
                    # Amplify audio before sending
                    processed_audio = self._amplify_audio(audio_data)
                    self.client.send_audio(processed_audio)
                    audio_chunks_sent += 1

                    # Log audio activity every 100 chunks (~6.4 seconds)
                    if audio_chunks_sent % 100 == 0:
                        print(f"🎵 Audio chunks sent: {audio_chunks_sent}")

            except Exception as e:
                print(f"⚠️ Audio streaming error: {e}")
                time.sleep(0.1)

    def _monitor_connection(self):
        """Monitor connection stability and attempt reconnection if needed"""
        while self.is_transcribing:
            time.sleep(5)  # Check every 5 seconds

            if self.last_heartbeat:
                time_since_heartbeat = (datetime.now() - self.last_heartbeat).seconds
                if time_since_heartbeat > 30:  # No activity for 30 seconds
                    print("⚠️ Connection seems inactive, checking stability...")
                    if not self.connection_stable:
                        self._attempt_reconnection()

    def _attempt_reconnection(self):
        """Attempt to reconnect to AssemblyAI Universal Streaming"""
        print("🔄 Attempting to reconnect to AssemblyAI Universal Streaming...")

        for attempt in range(self.max_reconnect_attempts):
            try:
                if self.client:
                    self.client.close()

                time.sleep(self.reconnect_delay)

                self.client = self.configure_realtime_transcription()
                self.client.connect(
                    StreamingParameters(
                        sample_rate=self.sample_rate,
                        format_turns=True,
                        speaker_labels=True  # Enable speaker diarization
                    )
                )

                print(f"✅ Reconnected to AssemblyAI Universal Streaming (attempt {attempt + 1})")
                return True

            except Exception as e:
                print(f"❌ Reconnection attempt {attempt + 1} failed: {e}")
                time.sleep(self.reconnect_delay * (attempt + 1))

        print("❌ Failed to reconnect after maximum attempts")
        if self.error_callback:
            self.error_callback("Failed to reconnect to AssemblyAI Universal Streaming")

        return False

    def stop_transcription(self):
        """Stop real-time transcription"""
        self.is_transcribing = False

        if self.client:
            try:
                self.client.disconnect(terminate=True)
            except Exception as e:
                print(f"⚠️ Error disconnecting client: {e}")

        if hasattr(self, 'streaming_thread'):
            self.streaming_thread.join(timeout=2)

        print("🛑 AssemblyAI transcription stopped")

    def get_speaker_statistics(self) -> Dict[str, Dict]:
        """Get statistics for all speakers"""
        stats = {}
        total_speaking_time = sum(s.total_speaking_time for s in self.speakers.values())

        for speaker_id, speaker in self.speakers.items():
            speaking_percentage = (speaker.total_speaking_time / total_speaking_time * 100) if total_speaking_time > 0 else 0

            stats[speaker.speaker_label] = {
                "message_count": speaker.message_count,
                "total_speaking_time": speaker.total_speaking_time,
                "speaking_percentage": speaking_percentage,
                "last_spoken": speaker.last_spoken.isoformat(),
                "words_per_message": speaker.total_speaking_time / speaker.message_count if speaker.message_count > 0 else 0
            }

        return stats

    def get_transcription_statistics(self) -> Dict[str, Any]:
        """Get overall transcription statistics"""
        duration = (datetime.now() - self.start_time).seconds if self.start_time else 0

        return {
            "total_duration": duration,
            "total_words": self.total_words_transcribed,
            "words_per_minute": (self.total_words_transcribed / (duration / 60)) if duration > 0 else 0,
            "speaker_count": len(self.speakers),
            "connection_stable": self.connection_stable,
            "is_transcribing": self.is_transcribing
        }

    def __del__(self):
        """Cleanup on destruction"""
        if self.is_transcribing:
            self.stop_transcription()

        if hasattr(self, 'audio'):
            self.audio.terminate()
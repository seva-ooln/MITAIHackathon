import os
import io
import tempfile
import threading
import time
from typing import Optional, Callable
import speech_recognition as sr
import pygame
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class VoiceHandler:
    """Handles voice input/output for the meeting bot"""

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.recognizer = sr.Recognizer()

        # Try to initialize microphone, handle Docker/no audio device case
        try:
            self.microphone = sr.Microphone()
        except OSError as e:
            print(f"Warning: No audio input device available: {e}")
            self.microphone = None

        # Initialize pygame mixer for audio playback
        self.mixer_available = False
        try:
            pygame.mixer.init()
            self.mixer_available = True
            print("✅ Audio output initialized successfully")
        except pygame.error as e:
            print(f"Warning: Audio output initialization failed: {e}")
            print("🔇 Running in silent mode - text output only")

        # Voice settings
        self.tts_voice = "alloy"  # OpenAI TTS voice options: alloy, echo, fable, onyx, nova, shimmer
        self.listening = False
        self.speech_callback: Optional[Callable] = None

        # Calibrate microphone
        self._calibrate_microphone()

    def _calibrate_microphone(self):
        """Calibrate microphone for ambient noise"""
        try:
            with self.microphone as source:
                print("🎤 Calibrating microphone for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                print("✅ Microphone calibrated")
        except Exception as e:
            print(f"⚠️ Microphone calibration failed: {e}")

    def text_to_speech(self, text: str) -> bool:
        """Convert text to speech using OpenAI TTS and play it"""
        try:
            # Check if mixer is available
            if not self.mixer_available:
                print("🔇 Audio not available - text only mode")
                return False

            response = self.client.audio.speech.create(
                model="tts-1",
                voice=self.tts_voice,
                input=text,
                speed=1.0
            )

            # Create temporary file for audio
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
                tmp_file.write(response.content)
                tmp_file_path = tmp_file.name

            # Play audio using pygame
            pygame.mixer.music.load(tmp_file_path)
            pygame.mixer.music.play()

            # Wait for playback to complete
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)

            # Stop music to release file handle
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            time.sleep(0.1)  # Small delay to ensure file is released

            # Clean up temporary file
            try:
                os.unlink(tmp_file_path)
            except PermissionError:
                # If file is still locked, try again after a short delay
                time.sleep(0.5)
                try:
                    os.unlink(tmp_file_path)
                except:
                    pass  # File will be cleaned up by system eventually

            return True

        except Exception as e:
            print(f"❌ TTS Error: {e}")
            return False

    def speech_to_text(self, audio_data) -> Optional[str]:
        """Convert speech to text using OpenAI Whisper"""
        try:
            # Save audio data to temporary WAV file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                tmp_file.write(audio_data.get_wav_data())
                tmp_file_path = tmp_file.name

            # Use OpenAI Whisper for transcription
            with open(tmp_file_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )

            # Clean up temporary file
            os.unlink(tmp_file_path)

            return transcript.strip() if transcript else None

        except Exception as e:
            print(f"❌ STT Error: {e}")
            return None

    def start_listening(self, callback: Callable[[str], None]):
        """Start continuous listening for speech"""
        self.speech_callback = callback
        self.listening = True

        def listen_continuously():
            while self.listening:
                try:
                    with self.microphone as source:
                        # Listen for audio with timeout
                        audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)

                    # Convert speech to text
                    text = self.speech_to_text(audio)

                    if text and len(text.strip()) > 0:
                        print(f"🎤 Heard: {text}")
                        if self.speech_callback:
                            self.speech_callback(text)

                except sr.WaitTimeoutError:
                    # No speech detected within timeout, continue listening
                    pass
                except Exception as e:
                    print(f"⚠️ Listening error: {e}")
                    time.sleep(1)

        # Start listening in background thread
        self.listen_thread = threading.Thread(target=listen_continuously, daemon=True)
        self.listen_thread.start()
        print("🎤 Started continuous listening...")

    def stop_listening(self):
        """Stop continuous listening"""
        self.listening = False
        print("🔇 Stopped listening")

    def speak(self, text: str):
        """Speak the given text (convenience method)"""
        print(f"🗣️ Bot: {text}")
        return self.text_to_speech(text)

    def set_voice(self, voice_name: str):
        """Change TTS voice"""
        valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        if voice_name in valid_voices:
            self.tts_voice = voice_name
            print(f"🔊 Voice changed to: {voice_name}")
        else:
            print(f"❌ Invalid voice. Available: {', '.join(valid_voices)}")

    def is_listening(self) -> bool:
        """Check if currently listening"""
        return self.listening

    def test_audio(self):
        """Test audio capabilities"""
        print("🔊 Testing audio capabilities...")

        # Test TTS
        test_text = "Hello! I am your meeting facilitator bot. Can you hear me clearly?"
        if self.speak(test_text):
            print("✅ Text-to-speech working")
        else:
            print("❌ Text-to-speech failed")

        # Test microphone
        try:
            with self.microphone as source:
                print("🎤 Say something to test the microphone...")
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=3)
                text = self.speech_to_text(audio)
                if text:
                    print(f"✅ Speech-to-text working. You said: '{text}'")
                    return True
                else:
                    print("❌ Speech-to-text failed")
                    return False
        except sr.WaitTimeoutError:
            print("⚠️ No speech detected during test")
            return False
        except Exception as e:
            print(f"❌ Microphone test failed: {e}")
            return False
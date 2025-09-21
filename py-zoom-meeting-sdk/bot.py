"""
Zoom Meeting SDK bot that joins a meeting and streams raw audio to AssemblyAI
for real-time transcription (testing path). This validates that we can pull
audio chunks from Zoom in real time and forward them in a compatible format.

Usage:
  - Ensure `.env` exists at repo root with:
      ZOOM_APP_CLIENT_ID=...
      ZOOM_APP_CLIENT_SECRET=...
      MEETING_ID=...
      MEETING_PWD=...
      (optional) DISPLAY_NAME=My Zoom Bot
      (optional) ASSEMBLYAI_API_KEY=...
  - Run inside the dev container: `python bot.py`

Notes:
  - Audio is received as 16-bit PCM little-endian mono, at 32 kHz from Zoom.
  - The AssemblyAI streaming session is configured for sample_rate=32000.
  - If `ASSEMBLYAI_API_KEY` is not set, the bot prints audio volume instead.
  - No video is sent; this focuses only on audio capture + streaming.
"""

from __future__ import annotations

import os
import signal
import sys
from datetime import datetime, timedelta
from typing import Optional
import threading
import queue

import jwt
from dotenv import load_dotenv

import zoom_meeting_sdk as zoom

import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib


def _generate_jwt(client_id: str, client_secret: str) -> str:
    iat = datetime.utcnow()
    exp = iat + timedelta(hours=24)
    payload = {
        "iat": iat,
        "exp": exp,
        "appKey": client_id,
        "tokenExp": int(exp.timestamp()),
    }
    return jwt.encode(payload, client_secret, algorithm="HS256")


class AssemblyAIStreamer:
    """Thin wrapper around AssemblyAI StreamingClient that pulls audio bytes
    from a queue and pushes to the streaming session.

    It runs the `stream` call in a background thread using a generator that
    yields queued audio chunks.
    """

    def __init__(self, api_key: str, sample_rate: int = 32000, format_turns: bool = True) -> None:
        self._api_key = api_key
        self._sample_rate = sample_rate
        self._format_turns = format_turns
        self._client = None
        self._queue: "queue.Queue[Optional[bytes]]" = queue.Queue(maxsize=100)
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._connected = False
        self._errors = []

        # Lazy import to avoid hard dependency during simple joins
        try:
            import assemblyai as aai  # noqa: F401
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
            self._aai = {
                'StreamingClient': StreamingClient,
                'StreamingClientOptions': StreamingClientOptions,
                'StreamingEvents': StreamingEvents,
                'StreamingParameters': StreamingParameters,
            }
        except Exception as e:
            raise RuntimeError(
                "assemblyai package not installed. Install with `pip install assemblyai`."
            ) from e

    def _make_client(self):
        SC = self._aai['StreamingClient']
        SCOpts = self._aai['StreamingClientOptions']
        client = SC(
            SCOpts(
                api_key=self._api_key,
                api_host="streaming.assemblyai.com",
            )
        )

        # Bind simple event handlers for visibility
        try:
            from assemblyai.streaming.v3 import (
                BeginEvent,
                StreamingError,
                StreamingEvents,
                StreamingSessionParameters,
                TerminationEvent,
                TurnEvent,
            )

            def on_begin(self_client: SC, event: BeginEvent):
                print(f"AssemblyAI session started: {event.id}")

            def on_turn(self_client: SC, event: TurnEvent):
                if event.transcript:
                    print(f"AAI: {event.transcript} (final={event.end_of_turn})")
                if event.end_of_turn and not event.turn_is_formatted:
                    try:
                        params = StreamingSessionParameters(format_turns=True)
                        self_client.set_params(params)
                    except Exception:
                        pass

            def on_terminated(self_client: SC, event: TerminationEvent):
                print(
                    f"AssemblyAI session terminated: {event.audio_duration_seconds} seconds processed"
                )

            def on_error(self_client: SC, error: StreamingError):
                print(f"AssemblyAI streaming error: {error}")

            client.on(StreamingEvents.Begin, on_begin)
            client.on(StreamingEvents.Turn, on_turn)
            client.on(StreamingEvents.Termination, on_terminated)
            client.on(StreamingEvents.Error, on_error)
        except Exception:
            pass

        return client

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._client = self._make_client()

        Params = self._aai['StreamingParameters']
        params = Params(sample_rate=self._sample_rate, format_turns=self._format_turns)
        self._client.connect(params)
        self._connected = True

        def _generator():
            while self._running:
                try:
                    chunk = self._queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                if chunk is None:
                    break
                yield chunk

        def _run():
            try:
                self._client.stream(_generator())
            except Exception as e:
                self._errors.append(e)
                print(f"AssemblyAI stream exception: {e}")
            finally:
                try:
                    if self._connected:
                        self._client.disconnect(terminate=True)
                except Exception:
                    pass
                self._connected = False

        self._thread = threading.Thread(target=_run, name="AssemblyAIStream", daemon=True)
        self._thread.start()

    def push(self, pcm_bytes: bytes) -> None:
        if not self._running:
            return
        try:
            self._queue.put_nowait(pcm_bytes)
        except queue.Full:
            # Drop chunk if backlog; we prefer real-time over backlog growth
            pass

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        try:
            if self._connected:
                self._client.disconnect(terminate=True)
        except Exception:
            pass
        self._connected = False

    def sample_rate(self) -> int:
        return self._sample_rate


class JoinOnlyBot:
    def __init__(self) -> None:
        self.meeting_service = None
        self.setting_service = None
        self.auth_service = None

        self.meeting_service_event = None
        self.auth_event = None

        self._main_loop: GLib.MainLoop | None = None

        # Meeting/audio state
        self.participants_ctrl = None
        self.my_participant_id = None
        self.audio_ctrl = None
        self.audio_ctrl_event = None
        self.recording_ctrl = None
        self.recording_event = None
        self.audio_helper = None
        self.audio_source = None

        # Meeting join status
        self.is_meeting_joined = False
        self.auth_successful = False

        # AAI streaming
        self.aai_streamer: Optional[AssemblyAIStreamer] = None
        self._aai_enabled = bool(os.environ.get('ASSEMBLYAI_API_KEY'))
        self._aai_buf = bytearray()
        self._aai_buf_lock = threading.Lock()
        self._aai_min_chunk_ms = 100  # send ~100ms chunks to satisfy AAI's 50-1000ms requirement

    # ----- lifecycle -----
    def init(self) -> None:
        # Validate env
        required = [
            'MEETING_ID',
            'MEETING_PWD',
            'ZOOM_APP_CLIENT_ID',
            'ZOOM_APP_CLIENT_SECRET',
        ]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f"Missing required env vars: {', '.join(missing)}. Define them in .env")

        init_param = zoom.InitParam()
        init_param.strWebDomain = "https://zoom.us"
        init_param.strSupportUrl = "https://zoom.us"
        init_param.enableGenerateDump = True
        init_param.emLanguageID = zoom.SDK_LANGUAGE_ID.LANGUAGE_English
        init_param.enableLogByDefault = True

        result = zoom.InitSDK(init_param)
        if result != zoom.SDKERR_SUCCESS:
            raise RuntimeError(f"InitSDK failed with code: {result}")

        self._create_services_and_auth()

    def leave_and_cleanup(self) -> None:
        try:
            if self.meeting_service:
                status = self.meeting_service.GetMeetingStatus()
                if status and status != zoom.MEETING_STATUS_IDLE:
                    self.meeting_service.Leave(zoom.LEAVE_MEETING)
        except Exception:
            pass

        try:
            if self.meeting_service:
                zoom.DestroyMeetingService(self.meeting_service)
        except Exception:
            pass
        try:
            if self.setting_service:
                zoom.DestroySettingService(self.setting_service)
        except Exception:
            pass
        try:
            if self.auth_service:
                zoom.DestroyAuthService(self.auth_service)
        except Exception:
            pass

        try:
            if self.aai_streamer:
                self.aai_streamer.stop()
        except Exception:
            pass

        try:
            zoom.CleanUPSDK()
        except Exception:
            pass

    def run_loop(self) -> None:
        self._main_loop = GLib.MainLoop()
        print("Running. Press Ctrl+C to exit.")
        self._main_loop.run()

    # ----- Zoom callbacks -----
    def _on_auth_return(self, result):
        if result == zoom.AUTHRET_SUCCESS:
            print("Auth successful; joining meeting...")
            self.auth_successful = True
            self._join_meeting()
        else:
            print(f"Auth failed: {result}")
            self.auth_successful = False
            self._quit()

    def _on_meeting_status_changed(self, status, iResult):
        print(f"Meeting status changed: status={status}, iResult={iResult}")
        if status == zoom.MEETING_STATUS_INMEETING:
            print("Joined meeting successfully.")
            self.is_meeting_joined = True
            self._on_join()

    def _on_user_audio_status_change(self, user_audio_statuses, other):
        print("Audio status changed.")

    def _on_user_active_audio_change(self, user_ids):
        # Called with active speakers; useful for diagnostics
        pass

    def _on_host_request_start_audio(self):
        print("Host requested to start audio")
        # Auto-accept host's request to start audio
        if self.audio_ctrl:
            self.audio_ctrl.JoinVoip()

    def _on_recording_privilege_changed(self, can_record):
        print(f"Recording privilege changed: {can_record}")
        if can_record:
            GLib.timeout_add_seconds(1, self._start_raw_recording)

    # ----- internals -----
    def _create_services_and_auth(self) -> None:
        self.meeting_service = zoom.CreateMeetingService()
        self.setting_service = zoom.CreateSettingService()
        self.auth_service = zoom.CreateAuthService()

        self.meeting_service_event = zoom.MeetingServiceEventCallbacks(
            onMeetingStatusChangedCallback=self._on_meeting_status_changed
        )
        set_evt = self.meeting_service.SetEvent(self.meeting_service_event)
        if set_evt != zoom.SDKERR_SUCCESS:
            raise RuntimeError("Failed to set meeting service event callbacks")

        self.auth_event = zoom.AuthServiceEventCallbacks(
            onAuthenticationReturnCallback=self._on_auth_return
        )
        auth_evt = self.auth_service.SetEvent(self.auth_event)
        if auth_evt != zoom.SDKERR_SUCCESS:
            raise RuntimeError("Failed to set auth service event callbacks")

        ctx = zoom.AuthContext()
        ctx.jwt_token = _generate_jwt(
            os.environ['ZOOM_APP_CLIENT_ID'],
            os.environ['ZOOM_APP_CLIENT_SECRET'],
        )
        res = self.auth_service.SDKAuth(ctx)
        if res == zoom.SDKError.SDKERR_SUCCESS:
            print("Authentication started...")
        else:
            raise RuntimeError(f"SDKAuth start failed: {res}")

    def _join_meeting(self) -> None:
        join_param = zoom.JoinParam()
        join_param.userType = zoom.SDKUserType.SDK_UT_WITHOUT_LOGIN

        param = join_param.param
        param.meetingNumber = int(os.environ['MEETING_ID'])
        param.userName = os.environ.get('DISPLAY_NAME', 'Python Zoom Bot')
        param.psw = os.environ['MEETING_PWD']
        # Join with audio allowed (we'll call JoinVoip), but keep video off
        param.isVideoOff = True
        param.isAudioOff = False
        # Match sample program behavior for raw audio params
        try:
            param.isAudioRawDataStereo = False
            param.isMyVoiceInMix = False
            param.eAudioRawdataSamplingRate = zoom.AudioRawdataSamplingRate.AudioRawdataSamplingRate_32K
        except Exception:
            pass
        
        result = self.meeting_service.Join(join_param)
        print(f"Join call returned: {result}")

    def _quit(self) -> None:
        try:
            if self._main_loop and self._main_loop.is_running():
                self._main_loop.quit()
        finally:
            self.leave_and_cleanup()

    # ----- meeting setup after join -----
    def _on_join(self):
        try:
            # Participants (to filter out self audio)
            self.participants_ctrl = self.meeting_service.GetMeetingParticipantsController()
            me = self.participants_ctrl.GetMySelfUser()
            self.my_participant_id = me.GetUserID() if me else None
        except Exception:
            self.participants_ctrl = None
            self.my_participant_id = None

        # Audio controller and VoIP
        self.audio_ctrl = self.meeting_service.GetMeetingAudioController()
        self.audio_ctrl_event = zoom.MeetingAudioCtrlEventCallbacks(
            onUserAudioStatusChangeCallback=self._on_user_audio_status_change,
            onUserActiveAudioChangeCallback=self._on_user_active_audio_change,
            onHostRequestStartAudioCallback=self._on_host_request_start_audio,
        )
        self.audio_ctrl.SetEvent(self.audio_ctrl_event)
        # Workaround per sample: call JoinVoip() before raw audio subscription
        self.audio_ctrl.JoinVoip()
        try:
            # Ensure our audio is unmuted so virtual mic can be heard
            if self.my_participant_id is not None:
                self.audio_ctrl.UnMuteAudio(self.my_participant_id)
                print("Bot unmuted successfully")
            else:
                print("Warning: Could not get participant ID for unmuting")
        except Exception as e:
            print(f"Failed to unmute bot: {e}")

        # Auto-join audio via settings
        try:
            audio_settings = self.setting_service.GetAudioSettings()
            audio_settings.EnableAutoJoinAudio(True)
        except Exception:
            pass

        # Recording controller (needed to enable raw audio helpers)
        self.recording_ctrl = self.meeting_service.GetMeetingRecordingController()
        self.recording_event = zoom.MeetingRecordingCtrlEventCallbacks(
            onRecordPrivilegeChangedCallback=self._on_recording_privilege_changed,
        )
        self.recording_ctrl.SetEvent(self.recording_event)

        # Start AAI streaming if configured
        if self._aai_enabled and not self.aai_streamer:
            try:
                self.aai_streamer = AssemblyAIStreamer(os.environ['ASSEMBLYAI_API_KEY'], sample_rate=32000)
                self.aai_streamer.start()
                print("AssemblyAI streaming started (32 kHz, PCM16 mono).")
            except Exception as e:
                print(f"Failed to start AssemblyAI streaming: {e}")
                self.aai_streamer = None

        # Try to start raw recording immediately; request privilege if needed
        GLib.timeout_add_seconds(1, self._start_raw_recording)

    def _start_raw_recording(self):
        try:
            can = self.recording_ctrl.CanStartRawRecording()
            if can != zoom.SDKERR_SUCCESS:
                self.recording_ctrl.RequestLocalRecordingPrivilege()
                print("Requested local recording privilege.")
                return False

            start = self.recording_ctrl.StartRawRecording()
            if start != zoom.SDKERR_SUCCESS:
                print(f"Start raw recording failed: {start}")
                return False

            self.audio_helper = zoom.GetAudioRawdataHelper()
            if self.audio_helper is None:
                print("Audio raw data helper is None")
                return False

            if self.audio_source is None:
                self.audio_source = zoom.ZoomSDKAudioRawDataDelegateCallbacks(
                    onOneWayAudioRawDataReceivedCallback=self._on_one_way_audio_raw_data_received,
                    collectPerformanceData=True,
                )

            sub = self.audio_helper.subscribe(self.audio_source, False)
            print(f"Audio raw data subscribe result: {sub}")
            return False  # don't repeat
        except Exception as e:
            print(f"Error starting raw recording: {e}")
            return False

    # Invoked for each user's mono stream (one-way audio)
    def _on_one_way_audio_raw_data_received(self, data, node_id):
        try:
            buf = data.GetBuffer()  # bytes, PCM16 LE mono
        except Exception as e:
            print(f"Failed to get audio buffer: {e}")
            return

        # If no AAI key, just print a rough volume metric occasionally
        if not self._aai_enabled or not self.aai_streamer:
            try:
                import array
                samples = array.array('h')
                samples.frombytes(buf)
                if not samples:
                    return
                # Simple RMS
                s2 = sum(int(x) * int(x) for x in samples)
                rms = (s2 / len(samples)) ** 0.5
                norm = rms / 32767.0
                if norm > 0.02:
                    name = None
                    try:
                        if self.participants_ctrl:
                            u = self.participants_ctrl.GetUserByUserID(node_id)
                            name = u.GetUserName() if u else None
                    except Exception:
                        pass
                    print(f"Audio from {name or node_id}: vol={norm:.2f}")
            except Exception:
                pass
            return

        # Only forward remote speakers (ignore our own mic stream if present)
        if self.my_participant_id is not None and node_id == self.my_participant_id:
            return

        # Accumulate audio to >=50ms chunks (we use ~100ms) before sending to AAI
        try:
            sr = self.aai_streamer.sample_rate() if self.aai_streamer else 32000
            min_bytes = int(self._aai_min_chunk_ms / 1000.0 * sr * 2)  # 16-bit mono
            with self._aai_buf_lock:
                self._aai_buf += buf
                while len(self._aai_buf) >= min_bytes:
                    chunk = bytes(self._aai_buf[:min_bytes])
                    del self._aai_buf[:min_bytes]
                    self.aai_streamer.push(chunk)
        except Exception as e:
            print(f"AAI buffering error: {e}")


def main() -> None:
    load_dotenv()

    bot = JoinOnlyBot()

    # Handle signals for a clean exit
    def _handle_signal(signum, frame):
        print(f"\nSignal received ({signum}); exiting...")
        bot._quit()
        os._exit(0)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        bot.init()
    except Exception as e:
        print(f"Initialization error: {e}")
        sys.exit(1)

    bot.run_loop()


if __name__ == "__main__":
    main()

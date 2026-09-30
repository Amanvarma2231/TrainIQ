"""
recorder.py – High-performance synchronized screen + audio recorder.
Uses:
  - mss        : fast cross-platform screen capture
  - OpenCV     : encode frames to XVID AVI
  - sounddevice: real-time microphone/loopback audio capture
  - FFmpeg     : merge video + audio into final MP4
"""
import os
import time
import wave
import threading
import numpy as np

try:
    import cv2
except Exception as _exc:
    cv2 = None

try:
    import mss
except Exception as _exc:
    mss = None

try:
    import sounddevice as sd
except Exception as _exc:
    sd = None

from utils import merge_video_audio


class ScreenAudioRecorder:
    """Records the primary monitor screen and a chosen audio input device."""

    RECORDINGS_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "recordings"
    )

    def __init__(self, fps: int = 20, sample_rate: int = 44100, channels: int = 1):
        os.makedirs(self.RECORDINGS_DIR, exist_ok=True)

        self.fps         = fps
        self.sample_rate = sample_rate
        self.channels    = channels

        self.is_recording = False
        self.is_paused    = False

        self._video_thread = None
        self._audio_thread = None

        self.start_time       = 0.0
        self.paused_duration  = 0.0
        self.pause_start      = 0.0
        self.elapsed_time     = 0.0   # populated on stop()

        self._temp_video = ""
        self._temp_audio = ""
        self.final_output = ""

        self.current_volume_level = 0.0   # 0.0–1.0, updated live

    # ------------------------------------------------------------------
    def get_audio_input_devices(self):
        """Returns list of (index, name) tuples for available audio inputs."""
        devices = []
        if sd is None:
            return devices
        try:
            for idx, dev in enumerate(sd.query_devices()):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append((idx, dev["name"]))
        except Exception:
            pass
        return devices

    # ------------------------------------------------------------------
    def start(self, filename_prefix: str = "TrainIQ", device_index: int | None = None):
        """Starts recording.  Safe to call only when not already recording."""
        if self.is_recording:
            return

        ts = time.strftime("%Y%m%d_%H%M%S")
        base = f"{filename_prefix}_{ts}"
        self._temp_video = os.path.join(self.RECORDINGS_DIR, f"_tmp_v_{base}.avi")
        self._temp_audio = os.path.join(self.RECORDINGS_DIR, f"_tmp_a_{base}.wav")
        self.final_output = os.path.join(self.RECORDINGS_DIR, f"{base}.mp4")

        self.is_recording    = True
        self.is_paused       = False
        self.start_time      = time.time()
        self.paused_duration = 0.0
        self.elapsed_time    = 0.0
        self.current_volume_level = 0.0

        self._video_thread = threading.Thread(target=self._record_screen,  daemon=True)
        self._audio_thread = threading.Thread(
            target=self._record_audio, args=(device_index,), daemon=True
        )
        self._video_thread.start()
        self._audio_thread.start()

    def pause(self):
        if self.is_recording and not self.is_paused:
            self.is_paused   = True
            self.pause_start = time.time()

    def resume(self):
        if self.is_recording and self.is_paused:
            self.paused_duration += time.time() - self.pause_start
            self.is_paused = False

    def get_elapsed_seconds(self) -> float:
        if not self.is_recording:
            return self.elapsed_time
        if self.is_paused:
            return self.pause_start - self.start_time - self.paused_duration
        return time.time() - self.start_time - self.paused_duration

    def stop(self) -> str:
        """Stops recording, merges video + audio into MP4, returns file path."""
        if not self.is_recording:
            return self.final_output

        self.elapsed_time = self.get_elapsed_seconds()
        self.is_recording = False
        self.is_paused    = False

        # Wait for threads to finish (give them a few seconds)
        if self._video_thread and self._video_thread.is_alive():
            self._video_thread.join(timeout=5.0)
        if self._audio_thread and self._audio_thread.is_alive():
            self._audio_thread.join(timeout=5.0)

        # Merge
        ok = merge_video_audio(self._temp_video, self._temp_audio, self.final_output)

        # Clean up temp files
        for tmp in (self._temp_video, self._temp_audio):
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass

        if ok and os.path.exists(self.final_output):
            return self.final_output
        if os.path.exists(self._temp_video):
            return self._temp_video
        return self.final_output

    # ------------------------------------------------------------------
    # Internal worker threads
    # ------------------------------------------------------------------
    def _record_screen(self):
        if mss is None or cv2 is None:
            print("[recorder] Screen recording not available in headless mode")
            return
        try:
            with mss.mss() as sct:
                monitor = dict(sct.monitors[1])  # primary monitor

                # Ensure even dimensions for the codec
                w = monitor["width"]  - (monitor["width"]  % 2)
                h = monitor["height"] - (monitor["height"] % 2)
                monitor["width"]  = w
                monitor["height"] = h

                fourcc = cv2.VideoWriter_fourcc(*"XVID")
                out = cv2.VideoWriter(
                    self._temp_video, fourcc, float(self.fps), (w, h)
                )

                frame_time = 1.0 / self.fps

                while self.is_recording:
                    t0 = time.time()
                    if not self.is_paused:
                        try:
                            img = np.array(sct.grab(monitor))
                            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                            out.write(frame)
                        except Exception as exc:
                            print(f"[recorder] screen frame error: {exc}")

                    sleep_dur = frame_time - (time.time() - t0)
                    if sleep_dur > 0:
                        time.sleep(sleep_dur)

                out.release()
        except Exception as exc:
            print(f"[recorder] screen recording error: {exc}")

    def _record_audio(self, device_index: int | None = None):
        if sd is None:
            print("[recorder] Audio recording not available in headless mode")
            return
        frames = []

        def _callback(indata, frame_count, time_info, status):
            if self.is_recording and not self.is_paused:
                frames.append(indata.copy())
                rms = float(np.sqrt(np.mean(indata ** 2)))
                self.current_volume_level = min(1.0, rms * 12.0)

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=_callback,
                device=device_index,
            ):
                while self.is_recording:
                    time.sleep(0.05)
        except Exception as exc:
            print(f"[recorder] audio error: {exc}")

        # Write WAV
        if frames:
            try:
                audio = np.concatenate(frames, axis=0)
                pcm   = (audio * 32767).astype(np.int16)
                with wave.open(self._temp_audio, "wb") as wf:
                    wf.setnchannels(self.channels)
                    wf.setsampwidth(2)
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(pcm.tobytes())
            except Exception as exc:
                print(f"[recorder] WAV write error: {exc}")

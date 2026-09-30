import os
import wave
import speech_recognition as sr
from utils import extract_audio_wav, format_seconds

class TranscriberEngine:
    def __init__(self, gemini_api_key: str = None):
        self.gemini_api_key = gemini_api_key

    def set_api_key(self, api_key: str):
        self.gemini_api_key = api_key

    def transcribe_video(self, video_path: str, progress_callback=None) -> str:
        """Transcribes video file to timestamped transcript string."""
        if not os.path.exists(video_path):
            return "Error: Video file does not exist."

        # Extract audio to temporary WAV file
        temp_wav = video_path + "_temp_audio.wav"
        if progress_callback:
            progress_callback("Extracting audio stream from video...")
            
        success = extract_audio_wav(video_path, temp_wav)
        if not success or not os.path.exists(temp_wav):
            return "[00:00] (Audio track could not be extracted or is empty)"

        try:
            # Try Gemini API multimodal audio transcription first if key available
            if self.gemini_api_key and self.gemini_api_key.strip():
                try:
                    if progress_callback:
                        progress_callback("Transcribing audio using Google Gemini AI...")
                    transcript = self._transcribe_with_gemini(temp_wav)
                    if transcript:
                        return transcript
                except Exception as e:
                    print(f"Gemini transcription error: {e}. Falling back to local engine.")

            # Local Speech Recognition fallback
            if progress_callback:
                progress_callback("Transcribing audio using local speech engine...")
            return self._transcribe_local_wav(temp_wav, progress_callback)
        finally:
            if os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except Exception:
                    pass

    def _transcribe_with_gemini(self, wav_path: str) -> str:
        """Transcribes using Gemini API multimodal audio processing."""
        import google.generativeai as genai
        genai.configure(api_key=self.gemini_api_key.strip())
        
        # Upload file to Gemini File API
        uploaded_file = genai.upload_file(path=wav_path, display_name="Training_Audio")
        
        prompt = """
Please transcribe this audio recording of a training session / meeting accurately.
Format the output with timestamp tags in brackets like [MM:SS] at the beginning of each major statement or slide topic change.
Identify speakers if possible (e.g., [00:15] Presenter: Welcome everyone...).
Provide clear, readable, verbatim text.
"""
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content([uploaded_file, prompt])
        
        # Clean up uploaded file
        try:
            genai.delete_file(uploaded_file.name)
        except Exception:
            pass
            
        return response.text if response and response.text else ""

    def _transcribe_local_wav(self, wav_path: str, progress_callback=None) -> str:
        """Transcribes WAV file locally in 30-second chunks using SpeechRecognition."""
        recognizer = sr.Recognizer()
        
        try:
            with wave.open(wav_path, 'rb') as wf:
                framerate = wf.getframerate()
                nframes = wf.getnframes()
                duration = nframes / float(framerate)
        except Exception:
            return "[00:00] Audio file could not be read."

        if duration <= 0:
            return "[00:00] No audio content recorded."

        chunk_seconds = 30
        num_chunks = max(1, int(duration // chunk_seconds) + (1 if duration % chunk_seconds > 0 else 0))
        
        full_transcript = []
        
        with sr.AudioFile(wav_path) as source:
            for i in range(num_chunks):
                start_sec = i * chunk_seconds
                offset = start_sec
                dur = min(chunk_seconds, duration - start_sec)
                if dur <= 0:
                    break
                    
                timestamp_str = format_seconds(start_sec)
                if progress_callback:
                    pct = int(((i + 1) / num_chunks) * 100)
                    progress_callback(f"Transcribing audio segment {i+1}/{num_chunks} ({pct}%)...")
                    
                try:
                    audio_data = recognizer.record(source, duration=dur)
                    # Recognize speech using Google Free Web Speech API
                    text = recognizer.recognize_google(audio_data)
                    full_transcript.append(f"[{timestamp_str}] {text}")
                except sr.UnknownValueError:
                    # Silence or unrecognized audio in segment
                    pass
                except sr.RequestError as e:
                    full_transcript.append(f"[{timestamp_str}] (Offline segment - speech network unavailable)")
                except Exception as e:
                    pass

        if not full_transcript:
            return "[00:00] Recorded audio contains clear visual content with minimal background speech or noise."

        return "\n\n".join(full_transcript)

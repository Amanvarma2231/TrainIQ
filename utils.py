import os
import sys
import subprocess
import time
import imageio_ffmpeg

def get_ffmpeg_path() -> str:
    """Returns absolute path to executable ffmpeg binary."""
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def format_seconds(seconds: float) -> str:
    """Formats seconds into HH:MM:SS or MM:SS."""
    seconds = int(seconds)
    hrs = seconds // 3600
    mins = (seconds % 3600) // 60
    secs = seconds % 60
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

def format_file_size(size_bytes: int) -> str:
    """Formats file size in bytes to human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def merge_video_audio(video_file: str, audio_file: str, output_file: str) -> bool:
    """Merges video and audio files into a single synced MP4 using ffmpeg."""
    ffmpeg_exe = get_ffmpeg_path()
    if not os.path.exists(video_file):
        return False
    
    cmd = [
        ffmpeg_exe,
        "-y",
        "-threads", "0",
        "-i", video_file,
    ]
    
    if os.path.exists(audio_file) and os.path.getsize(audio_file) > 0:
        cmd.extend(["-i", audio_file, "-c:v", "copy", "-c:a", "aac", "-shortest", output_file])
    else:
        cmd.extend(["-c:v", "copy", output_file])
        
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
        return res.returncode == 0 and os.path.exists(output_file)
    except Exception as e:
        print(f"Error merging video/audio: {e}")
        return False

def extract_audio_wav(input_video: str, output_wav: str) -> bool:
    """Extracts 16kHz mono WAV audio from video for transcription."""
    ffmpeg_exe = get_ffmpeg_path()
    if not os.path.exists(input_video):
        return False
        
    cmd = [
        ffmpeg_exe,
        "-y",
        "-threads", "0",
        "-i", input_video,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_wav
    ]
    
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
        return res.returncode == 0 and os.path.exists(output_wav)
    except Exception as e:
        print(f"Error extracting audio: {e}")
        return False

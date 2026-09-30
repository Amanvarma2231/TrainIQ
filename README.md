# TrainIQ 🎙️💻🤖

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flet](https://img.shields.io/badge/Flet-1.0%2B-6C63FF?style=for-the-badge&logo=flutter&logoColor=white)
![Gemini AI](https://img.shields.io/badge/Google%20Gemini-AI-4285F4?style=for-the-badge&logo=google&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**Enterprise-Grade AI Training Recorder, Summarizer & Presentation Generator**

*Developed for Druidot Consulting Private Limited – Python Development Internship*

</div>

---

## 📌 What is TrainIQ?

**TrainIQ** is a professional desktop application built with **Python & Flet** that:

- 🎥 **Records** your entire screen + microphone audio simultaneously (Google Meet, YouTube, Zoom, any video)
- 🤖 **Transcribes** audio to timestamped text using Google Gemini AI (or free local fallback)
- 🧠 **Summarizes** sessions into structured executive notes, topics, takeaways & action items
- 💬 **Answers** any question you ask about the recording (AI Q&A chatbot)
- 📄 **Exports** a formatted PDF executive report with one click
- 📊 **Generates** a professional 16:9 PowerPoint presentation with one click
- 🗂️ **Stores** all sessions in a local SQLite library for anytime re-access

---

## 🌟 Features at a Glance

| Feature | Details |
|---|---|
| 🎬 Screen Recording | Full HD screen capture via MSS + OpenCV (20fps) |
| 🎙️ Audio Recording | Microphone input via sounddevice, real-time volume meter |
| ⏱️ Live Timer | Accurate HH:MM:SS recording counter with pause/resume |
| 📝 AI Transcription | Gemini 1.5 Flash multimodal OR Google Speech Recognition fallback |
| 🧠 AI Summary | Executive overview, timestamped agenda, key takeaways, action items |
| 💬 AI Q&A Chat | Context-aware chatbot with session memory & quick prompts |
| 📄 PDF Export | ReportLab-powered corporate report with styling & full transcript |
| 📊 PPTX Export | python-pptx 16:9 deck: Title, Summary, Topics, Takeaways, Actions |
| 🗃️ Session Library | Persistent SQLite DB with play/export/delete per session |
| ⚙️ Settings | Gemini API key management with live validation |

---

## 🏗️ Architecture & Project Structure

```
TrainIQ/
├── main.py              # Flet GUI – NavigationRail + 5 views (Recorder / Library / Summary / Q&A / Settings)
├── recorder.py          # Screen & Audio Recording Engine (MSS · sounddevice · FFmpeg merge)
├── transcriber.py       # Speech-to-Text Engine (Gemini AI multimodal + SpeechRecognition fallback)
├── ai_engine.py         # AI Summary Generator & Interactive Q&A Engine (Gemini + local fallback)
├── pdf_generator.py     # PDF Report Generator (ReportLab)
├── ppt_generator.py     # PowerPoint Generator (python-pptx)
├── database.py          # SQLite Persistence Layer (recordings · qna_history · settings)
├── utils.py             # FFmpeg helpers · format utilities · audio/video merge
├── requirements.txt     # Python package dependencies
├── recordings/          # Auto-created: saved MP4 session recordings
├── exports/             # Auto-created: generated PDF & PPTX exports
└── README.md            # This documentation file
```

---

## 💻 Installation & Quick Start

### Prerequisites
- **Python 3.10 or higher** (tested on Python 3.13)
- Windows 10/11, macOS, or Linux
- Internet connection (for Gemini AI features – offline fallback always available)

### 1 – Clone the Repository
```bash
git clone https://github.com/Amanvarma2231/TrainIQ.git
cd TrainIQ
```

### 2 – Install Dependencies
```bash
pip install -r requirements.txt
```

### 3 – Launch
```bash
python main.py
```

The app window opens immediately. No configuration required to start recording.

---

## 🔑 Gemini AI Setup (Optional – Enhances Accuracy Significantly)

TrainIQ works fully in **offline mode** with local speech recognition. To enable the Google Gemini AI for superior transcription and intelligent summaries:

1. Get a free API key at [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Open TrainIQ → click **⚙ Settings** in the sidebar
3. Paste your key → click **Save API Key**

That's it — all AI features activate automatically.

---

## 🖥️ How to Use

### Recording a Session
1. Navigate to **🎥 Recorder** tab
2. Enter a session title (e.g. "Python Masterclass – Day 3")
3. Select microphone from the dropdown
4. Click **Start Recording** — TrainIQ captures your full screen + audio
5. Open your Google Meet / YouTube / Zoom session normally
6. Click **Stop & Save** when done

### Viewing Results
- **📚 Library** — All sessions listed with duration, file size, date. Play video, export PDF/PPTX, or delete.
- **✨ Summary** — 3-panel view: Executive Summary / Agenda Topics / Full Transcript. One-click PDF and PPTX export buttons.
- **🤖 AI Q&A** — Chat with your recording. Ask anything: "What did they say about neural networks?" / "List all action items" etc.

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `flet>=1.0.0` | Desktop GUI framework |
| `opencv-python` | Video frame encoding (XVID) |
| `mss` | Fast cross-platform screen capture |
| `sounddevice` | Real-time microphone recording |
| `imageio-ffmpeg` | FFmpeg binary for audio/video merging |
| `numpy` | Audio buffer processing |
| `speechrecognition` | Local speech-to-text fallback |
| `google-generativeai` | Gemini AI transcription, summary & Q&A |
| `reportlab` | PDF report generation |
| `python-pptx` | PowerPoint presentation generation |

---

## 🔧 Tech Stack

```
Backend  : Python 3.10+
GUI      : Flet 1.0 (Flutter-based cross-platform desktop)
AI       : Google Gemini 1.5 Flash (multimodal audio + text)
Video    : MSS + OpenCV + FFmpeg
Audio    : sounddevice + wave + SpeechRecognition
Database : SQLite3 (via Python standard library)
PDF      : ReportLab 4.x
PPTX     : python-pptx 0.6.x
```

---

## 📁 Output Files

All outputs are auto-saved locally:

- **Recordings**: `recordings/TrainIQ_YYYYMMDD_HHMMSS.mp4`
- **PDF Reports**: `exports/TrainIQ_Report_<ID>_<Title>.pdf`
- **PPTX Decks**: `exports/TrainIQ_Presentation_<ID>_<Title>.pptx`

---

## 👥 Credits

| | |
|---|---|
| **Company** | Druidot Consulting Private Limited |
| **Project** | Python Development Internship – TrainIQ |
| **Developer** | Aman Varma |
| **Tech Stack** | Python · Flet · Gemini AI · OpenCV · SQLite · ReportLab · python-pptx |

---

## 📄 License

This project is developed as part of the Druidot Consulting internship program.  
MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
  <b>TrainIQ</b> — Record. Transcribe. Summarize. Present. 🚀
</div>

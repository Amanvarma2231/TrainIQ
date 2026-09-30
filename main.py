"""
TrainIQ - Enterprise AI Training Session Recorder & Summarizer
============================================================
Company   : Druidot Consulting Private Limited
Internship: Python Development
Tech Stack: Python, Flet 1.0.x, OpenCV, sounddevice, Google Gemini AI,
            ReportLab (PDF), python-pptx (Presentation), SQLite

Features:
  1. Screen + Audio recording (PC-wide, captures Google Meet/Video/YouTube)
  2. AI Speech-to-Text transcription with timestamps (Gemini + local fallback)
  3. Structured AI summary  (Executive / Topics / Takeaways / Action Items / Q&A)
  4. Interactive AI Q&A chatbot (ask anything about recorded session)
  5. 1-Click PDF executive report export
  6. 1-Click PowerPoint (.pptx) presentation export
  7. Persistent SQLite session library
  8. Gemini API settings screen
"""

import os
import sys
import time
import threading
import subprocess
import flet as ft

from utils import format_seconds, format_file_size
import database as db
from recorder import ScreenAudioRecorder
from transcriber import TranscriberEngine
from ai_engine import AIEngine
from pdf_generator import PDFReportGenerator
from ppt_generator import PPTXGenerator


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER: open a file in the OS default application (cross-platform)
# ─────────────────────────────────────────────────────────────────────────────
def open_file_os(filepath: str):
    if not filepath or not os.path.exists(filepath):
        return
    try:
        if sys.platform == "win32":
            os.startfile(filepath)
        elif sys.platform == "darwin":
            subprocess.run(["open", filepath])
        else:
            subprocess.run(["xdg-open", filepath])
    except Exception as exc:
        print(f"[open_file_os] {exc}")


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN APP CLASS
# ─────────────────────────────────────────────────────────────────────────────
class TrainIQApp:
    def __init__(self, page: ft.Page):
        self.page = page

        # ── Window / theme setup ──────────────────────────────────────────────
        self.page.title = "TrainIQ – AI Training Recorder & Presentation Generator"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.theme = ft.Theme(
            color_scheme_seed=ft.Colors.INDIGO,
        )
        self.page.window.width = 1280
        self.page.window.height = 820
        self.page.window.min_width = 1024
        self.page.window.min_height = 700
        self.page.padding = 0
        self.page.bgcolor = ft.Colors.GREY_900

        # ── Bootstrap DB ──────────────────────────────────────────────────────
        db.init_db()

        # ── Engine init ───────────────────────────────────────────────────────
        gemini_key = db.get_setting("gemini_api_key", "")
        self.recorder       = ScreenAudioRecorder()
        self.transcriber    = TranscriberEngine(gemini_api_key=gemini_key)
        self.ai_engine      = AIEngine(gemini_api_key=gemini_key)
        self.pdf_gen        = PDFReportGenerator()
        self.ppt_gen        = PPTXGenerator()

        # ── State ─────────────────────────────────────────────────────────────
        self.selected_recording_id: int | None = None
        self.is_processing = False

        # ── Build UI ──────────────────────────────────────────────────────────
        self._build_shared_controls()
        self._load_last_session()
        self._render_layout()

    # =========================================================================
    #  TOAST / NOTIFICATION
    # =========================================================================
    def toast(self, message: str, color=ft.Colors.GREEN_700):
        """Shows a brief bottom SnackBar notification."""
        sb = ft.SnackBar(
            content=ft.Row([
                ft.Icon(ft.Icons.INFO_OUTLINED, color=ft.Colors.WHITE, size=18),
                ft.Text(f"  {message}", color=ft.Colors.WHITE,
                        weight=ft.FontWeight.W_600, size=13),
            ]),
            bgcolor=color,
            duration=3500,
        )
        self.page.overlay.append(sb)
        sb.open = True
        self.page.update()

    # =========================================================================
    #  SHARED CONTROLS (shared state across views)
    # =========================================================================
    def _build_shared_controls(self):
        # ── Recorder tab ──────────────────────────────────────────────────────
        self.txt_title = ft.TextField(
            label="Session Title / Topic",
            value="Google Video & Training Session",
            hint_text="e.g. Python Masterclass, Team Meeting, Google Meet",
            expand=True,
        )

        audio_devices = self.recorder.get_audio_input_devices()
        dev_opts = ([ft.dropdown.Option(str(i), n) for i, n in audio_devices]
                    or [ft.dropdown.Option("0", "Default Microphone")])
        self.dd_device = ft.Dropdown(
            label="Microphone",
            options=dev_opts,
            value=dev_opts[0].key if dev_opts else "0",
            width=300,
        )

        self.lbl_timer  = ft.Text("00:00:00", size=52,
                                   weight=ft.FontWeight.BOLD,
                                   color=ft.Colors.INDIGO_300)
        self.lbl_status = ft.Text("● READY", size=14,
                                   weight=ft.FontWeight.BOLD,
                                   color=ft.Colors.GREY_500)
        self.prg_volume = ft.ProgressBar(value=0.0, width=340,
                                          color=ft.Colors.GREEN_400,
                                          bgcolor=ft.Colors.GREY_800)
        self.lbl_vol_label = ft.Text("Mic Level", size=11,
                                      color=ft.Colors.GREY_500)

        self.btn_start  = ft.FilledButton(
            "Start Recording",
            icon=ft.Icons.FIBER_MANUAL_RECORD,
            style=ft.ButtonStyle(bgcolor=ft.Colors.RED_600,
                                  color=ft.Colors.WHITE),
            on_click=self._on_start,
        )
        self.btn_pause  = ft.OutlinedButton(
            "Pause", icon=ft.Icons.PAUSE,
            visible=False, on_click=self._on_pause,
        )
        self.btn_stop   = ft.FilledButton(
            "Stop & Save",
            icon=ft.Icons.STOP_CIRCLE,
            style=ft.ButtonStyle(bgcolor=ft.Colors.GREY_700,
                                  color=ft.Colors.WHITE),
            visible=False, on_click=self._on_stop,
        )

        self.prg_processing = ft.ProgressBar(width=400, visible=False)
        self.lbl_processing = ft.Text("", size=12, color=ft.Colors.INDIGO_300,
                                       visible=False)

        # ── Q&A tab ───────────────────────────────────────────────────────────
        self.chat_list   = ft.ListView(expand=True, spacing=10,
                                        padding=ft.Padding(left=8, top=12, right=8, bottom=12),
                                        auto_scroll=True)
        self.txt_question = ft.TextField(
            hint_text="Ask anything about the recorded session…",
            expand=True,
            shift_enter=True,
            multiline=True,
            max_lines=3,
            on_submit=self._on_send_chat,
        )
        self.btn_send = ft.IconButton(
            icon=ft.Icons.SEND_ROUNDED,
            icon_color=ft.Colors.INDIGO_400,
            tooltip="Send",
            on_click=self._on_send_chat,
        )

        # ── Settings tab ──────────────────────────────────────────────────────
        self.txt_api_key = ft.TextField(
            label="Google Gemini API Key",
            value=db.get_setting("gemini_api_key", ""),
            password=True,
            can_reveal_password=True,
            expand=True,
            hint_text="AIzaSy…",
        )

        # ── Navigation rail ───────────────────────────────────────────────────
        self.nav_rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=90,
            bgcolor=ft.Colors.GREY_800 if hasattr(ft.Colors, 'GREY_850') else ft.Colors.GREY_800,
            group_alignment=-0.9,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.VIDEOCAM_OUTLINED,
                    selected_icon=ft.Icons.VIDEOCAM,
                    label="Recorder",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.VIDEO_LIBRARY_OUTLINED,
                    selected_icon=ft.Icons.VIDEO_LIBRARY,
                    label="Library",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.AUTO_AWESOME_OUTLINED,
                    selected_icon=ft.Icons.AUTO_AWESOME,
                    label="Summary",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.CHAT_BUBBLE_OUTLINE,
                    selected_icon=ft.Icons.CHAT_BUBBLE,
                    label="AI Q&A",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    selected_icon=ft.Icons.SETTINGS,
                    label="Settings",
                ),
            ],
            on_change=self._on_nav_change,
        )

        # Main body container (swapped per tab)
        self.body = ft.Container(
            content=self._view_recorder(),
            expand=True,
            padding=20,
        )

    # =========================================================================
    #  LAYOUT
    # =========================================================================
    def _render_layout(self):
        self.page.add(
            ft.Row(
                [
                    self.nav_rail,
                    ft.VerticalDivider(width=1, color=ft.Colors.GREY_800),
                    self.body,
                ],
                expand=True,
                spacing=0,
            )
        )

    def _on_nav_change(self, e):
        idx = e.control.selected_index
        views = [
            self._view_recorder,
            self._view_library,
            self._view_summary,
            self._view_qna,
            self._view_settings,
        ]
        self.body.content = views[idx]()
        self.page.update()

    def _load_last_session(self):
        recs = db.get_recordings()
        if recs:
            self.selected_recording_id = recs[0]["id"]

    # =========================================================================
    #  VIEW 1 – RECORDER
    # =========================================================================
    def _view_recorder(self) -> ft.Control:
        return ft.Column(
            [
                # ── Header ────────────────────────────────────────────────────
                ft.Row([
                    ft.Icon(ft.Icons.VIDEOCAM, color=ft.Colors.RED_400, size=28),
                    ft.Column([
                        ft.Text("TrainIQ Studio", size=24, weight=ft.FontWeight.BOLD),
                        ft.Text(
                            "Record screen + audio from any training, Google Meet, or YouTube session",
                            size=12, color=ft.Colors.GREY_500,
                        ),
                    ], spacing=0),
                ], spacing=10),
                ft.Divider(color=ft.Colors.GREY_800, height=24),

                # ── Session config card ───────────────────────────────────────
                ft.Card(
                    content=ft.Container(
                        padding=20,
                        content=ft.Column([
                            ft.Text("Session Configuration", size=14,
                                     weight=ft.FontWeight.BOLD,
                                     color=ft.Colors.INDIGO_300),
                            ft.Container(height=8),
                            ft.Row([self.txt_title], expand=True),
                            ft.Container(height=10),
                            ft.Row([
                                self.dd_device,
                                ft.Container(width=20),
                                ft.Column([
                                    self.lbl_vol_label,
                                    self.prg_volume,
                                ], spacing=4),
                            ]),
                        ], spacing=0),
                    ),
                    elevation=2,
                ),
                ft.Container(height=12),

                # ── Status / controls card ────────────────────────────────────
                ft.Card(
                    content=ft.Container(
                        padding=30,
                        content=ft.Column(
                            [
                                self.lbl_timer,
                                self.lbl_status,
                                ft.Container(height=20),
                                ft.Row(
                                    [self.btn_start, self.btn_pause, self.btn_stop],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    spacing=12,
                                ),
                                ft.Container(height=16),
                                self.prg_processing,
                                self.lbl_processing,
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=4,
                        ),
                    ),
                    elevation=4,
                ),
                ft.Container(height=16),

                # ── Tips card ─────────────────────────────────────────────────
                ft.Card(
                    content=ft.Container(
                        padding=14,
                        content=ft.Row([
                            ft.Icon(ft.Icons.LIGHTBULB, color=ft.Colors.AMBER_400, size=20),
                            ft.Text(
                                "Pro tip: Start recording before joining your "
                                "Google Meet/Video or YouTube session. "
                                "TrainIQ will automatically transcribe, summarise, "
                                "and generate PDF & PowerPoint reports when you stop.",
                                size=12, color=ft.Colors.GREY_400,
                                expand=True,
                            ),
                        ], spacing=10),
                    ),
                    elevation=1,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
        )

    # ── Recording actions ─────────────────────────────────────────────────────
    def _on_start(self, e):
        if self.recorder.is_recording:
            return
        dev_idx = None
        try:
            dev_idx = int(self.dd_device.value)
        except Exception:
            pass

        title = self.txt_title.value.strip() or "Training Session"
        self.recorder.start(filename_prefix="TrainIQ", device_index=dev_idx)

        self.btn_start.visible = False
        self.btn_pause.visible = True
        self.btn_stop.visible  = True
        self.lbl_status.value  = "● RECORDING…"
        self.lbl_status.color  = ft.Colors.RED_400
        self.page.update()

        threading.Thread(target=self._timer_loop, daemon=True).start()
        self.toast("🔴 Recording started!", ft.Colors.RED_700)

    def _on_pause(self, e):
        if self.recorder.is_paused:
            self.recorder.resume()
            self.btn_pause.text  = "Pause"
            self.btn_pause.icon  = ft.Icons.PAUSE
            self.lbl_status.value = "● RECORDING…"
            self.lbl_status.color = ft.Colors.RED_400
        else:
            self.recorder.pause()
            self.btn_pause.text  = "Resume"
            self.btn_pause.icon  = ft.Icons.PLAY_ARROW
            self.lbl_status.value = "⏸ PAUSED"
            self.lbl_status.color = ft.Colors.AMBER_400
        self.page.update()

    def _on_stop(self, e):
        if not self.recorder.is_recording:
            return

        self.btn_pause.visible  = False
        self.btn_stop.visible   = False
        self.prg_processing.visible = True
        self.lbl_processing.visible = True
        self.lbl_status.value = "⏳ Saving recording…"
        self.lbl_status.color = ft.Colors.AMBER_400
        self.page.update()

        def _process():
            try:
                title = self.txt_title.value.strip() or "Training Session"

                # 1) Stop recorder → get output MP4
                self._set_progress("Merging video & audio…")
                output_mp4 = self.recorder.stop()
                duration   = self.recorder.elapsed_time
                file_size  = os.path.getsize(output_mp4) if os.path.exists(output_mp4) else 0

                # 2) Save to DB immediately (so user can see in library)
                rec_id = db.save_recording(title, output_mp4, duration, file_size)
                self.selected_recording_id = rec_id

                # 3) Transcribe
                self._set_progress("🤖 Transcribing audio…")
                transcript = self.transcriber.transcribe_video(
                    output_mp4,
                    progress_callback=self._set_progress,
                )
                db.update_recording(rec_id, transcript=transcript)

                # 4) AI Summary
                self._set_progress("🧠 Generating AI summary…")
                summary = self.ai_engine.generate_summary(transcript, title)
                db.update_recording(rec_id, summary=summary)

                # 5) Auto-export PDF + PPTX
                self._set_progress("📄 Generating PDF & PowerPoint…")
                rec_data = db.get_recording(rec_id)
                try:
                    self.pdf_gen.generate_pdf(rec_data)
                    self.ppt_gen.generate_presentation(rec_data)
                except Exception as ex:
                    print(f"Export error: {ex}")

                # 6) Reset UI
                self._reset_recorder_ui()
                self.toast("✅ Session saved! PDF & Presentation ready.", ft.Colors.GREEN_700)

                # Auto-switch to Summary view
                self.nav_rail.selected_index = 2
                self.body.content = self._view_summary()
                self.page.update()
            except RuntimeError:
                # Session closed while processing – save is already done in DB
                pass
            except Exception as ex:
                print(f"[_process] {ex}")

        threading.Thread(target=_process, daemon=True).start()

    def _set_progress(self, msg: str):
        try:
            self.lbl_processing.value = msg
            self.lbl_status.value = msg
            self.page.update()
        except RuntimeError:
            pass

    def _reset_recorder_ui(self):
        self.lbl_timer.value         = "00:00:00"
        self.lbl_status.value        = "● READY"
        self.lbl_status.color        = ft.Colors.GREY_500
        self.prg_volume.value        = 0.0
        self.btn_start.visible       = True
        self.btn_pause.visible       = False
        self.btn_stop.visible        = False
        self.prg_processing.visible  = False
        self.lbl_processing.visible  = False
        self.lbl_processing.value    = ""
        self.btn_pause.text          = "Pause"
        self.btn_pause.icon          = ft.Icons.PAUSE
        self.page.update()


    def _timer_loop(self):
        while self.recorder.is_recording:
            try:
                elapsed = self.recorder.get_elapsed_seconds()
                self.lbl_timer.value  = format_seconds(elapsed)
                self.prg_volume.value = min(1.0, self.recorder.current_volume_level)
                self.page.update()
            except RuntimeError:
                # Session destroyed (window closed) – exit thread cleanly
                break
            except Exception:
                break
            time.sleep(0.5)


    # =========================================================================
    #  VIEW 2 – LIBRARY
    # =========================================================================
    def _view_library(self) -> ft.Control:
        recordings = db.get_recordings()

        if not recordings:
            return ft.Column([
                ft.Container(height=40),
                ft.Row([ft.Icon(ft.Icons.VIDEO_LIBRARY_OUTLINED,
                                color=ft.Colors.GREY_700, size=64)],
                        justify_content=ft.MainAxisAlignment.CENTER),
                ft.Container(height=16),
                ft.Row([ft.Text("No recordings yet.",
                                size=18, color=ft.Colors.GREY_600)],
                        justify_content=ft.MainAxisAlignment.CENTER),
                ft.Row([ft.Text("Record your first training session "
                                "in the Recorder tab.",
                                size=13, color=ft.Colors.GREY_700)],
                        justify_content=ft.MainAxisAlignment.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        rows = []
        for r in recordings:
            rid = r["id"]
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(f"#{rid}", weight=ft.FontWeight.BOLD,
                                     color=ft.Colors.INDIGO_300)),
                ft.DataCell(ft.Text(r["title"], max_lines=1,
                                     overflow=ft.TextOverflow.ELLIPSIS)),
                ft.DataCell(ft.Text(format_seconds(r["duration"]))),
                ft.DataCell(ft.Text(format_file_size(r["file_size"]))),
                ft.DataCell(ft.Text((r["recorded_at"] or "")[:16],
                                     color=ft.Colors.GREY_400)),
                ft.DataCell(ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.AUTO_AWESOME,
                        icon_color=ft.Colors.INDIGO_400,
                        icon_size=18,
                        tooltip="View Summary",
                        on_click=lambda e, rid=rid: self._open_summary(rid),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.PLAY_CIRCLE_OUTLINED,
                        icon_color=ft.Colors.BLUE_400,
                        icon_size=18,
                        tooltip="Play Video",
                        on_click=lambda e, fp=r["file_path"]: open_file_os(fp),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.PICTURE_AS_PDF,
                        icon_color=ft.Colors.RED_400,
                        icon_size=18,
                        tooltip="Export PDF",
                        on_click=lambda e, rid=rid: self._export_pdf(rid),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.SLIDESHOW,
                        icon_color=ft.Colors.AMBER_400,
                        icon_size=18,
                        tooltip="Export PPTX",
                        on_click=lambda e, rid=rid: self._export_pptx(rid),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=ft.Colors.RED_300,
                        icon_size=18,
                        tooltip="Delete",
                        on_click=lambda e, rid=rid: self._delete_session(rid),
                    ),
                ], spacing=0)),
            ]))

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID")),
                ft.DataColumn(ft.Text("Title")),
                ft.DataColumn(ft.Text("Duration")),
                ft.DataColumn(ft.Text("Size")),
                ft.DataColumn(ft.Text("Recorded")),
                ft.DataColumn(ft.Text("Actions")),
            ],
            rows=rows,
            border=ft.Border.all(1, ft.Colors.GREY_800),
            border_radius=8,
            horizontal_lines=ft.BorderSide(0.5, ft.Colors.GREY_800),
        )

        return ft.Column(
            [
                ft.Row([
                    ft.Icon(ft.Icons.VIDEO_LIBRARY, color=ft.Colors.INDIGO_400, size=26),
                    ft.Text("Training Library", size=22, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.Text(f"{len(recordings)} session(s)",
                             size=13, color=ft.Colors.GREY_500),
                ], spacing=10),
                ft.Divider(color=ft.Colors.GREY_800, height=24),
                ft.Container(
                    content=ft.Column([table], scroll=ft.ScrollMode.AUTO),
                    expand=True,
                ),
            ],
            expand=True,
        )

    def _open_summary(self, recording_id: int):
        self.selected_recording_id = recording_id
        self.nav_rail.selected_index = 2
        self.body.content = self._view_summary()
        self.page.update()

    def _export_pdf(self, recording_id: int):
        rec = db.get_recording(recording_id)
        if not rec:
            return
        try:
            path = self.pdf_gen.generate_pdf(rec)
            self.toast(f"📄 PDF saved: {os.path.basename(path)}", ft.Colors.GREEN_700)
            open_file_os(path)
        except Exception as ex:
            self.toast(f"PDF error: {ex}", ft.Colors.RED_700)

    def _export_pptx(self, recording_id: int):
        rec = db.get_recording(recording_id)
        if not rec:
            return
        try:
            path = self.ppt_gen.generate_presentation(rec)
            self.toast(f"📊 PPTX saved: {os.path.basename(path)}", ft.Colors.AMBER_700)
            open_file_os(path)
        except Exception as ex:
            self.toast(f"PPTX error: {ex}", ft.Colors.RED_700)

    def _delete_session(self, recording_id: int):
        db.delete_recording(recording_id)
        if self.selected_recording_id == recording_id:
            recs = db.get_recordings()
            self.selected_recording_id = recs[0]["id"] if recs else None
        self.toast("Session deleted.", ft.Colors.RED_700)
        self.body.content = self._view_library()
        self.page.update()

    # =========================================================================
    #  VIEW 3 – SUMMARY
    # =========================================================================
    def _view_summary(self) -> ft.Control:
        rec = db.get_recording(self.selected_recording_id) if self.selected_recording_id else None

        if not rec:
            return ft.Column([
                ft.Container(height=50),
                ft.Row([ft.Icon(ft.Icons.AUTO_AWESOME_OUTLINED,
                                color=ft.Colors.GREY_700, size=64)],
                        justify_content=ft.MainAxisAlignment.CENTER),
                ft.Container(height=16),
                ft.Row([ft.Text("No session selected.", size=18,
                                 color=ft.Colors.GREY_600)],
                        justify_content=ft.MainAxisAlignment.CENTER),
                ft.Row([ft.FilledButton(
                    "Go to Library", icon=ft.Icons.VIDEO_LIBRARY,
                    on_click=lambda e: self._switch_to(1)
                )], justify_content=ft.MainAxisAlignment.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        title      = rec.get("title", "Training Program")
        summary    = rec.get("summary", {}) or {}
        transcript = rec.get("transcript", "") or ""

        # ── Sub-views (3 panels, switched by custom tab row) ──────────────────
        panels = [
            self._build_exec_panel(summary),
            self._build_topics_panel(summary),
            self._build_transcript_panel(transcript),
        ]
        sub_container = ft.Container(content=panels[0], expand=True)

        tab_info = [
            (ft.Icons.SUMMARIZE,  "Executive Summary"),
            (ft.Icons.LIST_ALT,   "Agenda Topics"),
            (ft.Icons.DESCRIPTION,"Full Transcript"),
        ]

        def _make_tabs(active: int) -> list:
            result = []
            for i, (icon, label) in enumerate(tab_info):
                if i == active:
                    result.append(ft.FilledButton(
                        label, icon=icon,
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.INDIGO_700,
                            color=ft.Colors.WHITE,
                        ),
                        on_click=lambda e, idx=i: _switch_tab(idx),
                    ))
                else:
                    result.append(ft.OutlinedButton(
                        label, icon=icon,
                        on_click=lambda e, idx=i: _switch_tab(idx),
                    ))
            return result

        tab_row = ft.Row(controls=_make_tabs(0), spacing=8)

        def _switch_tab(idx: int):
            tab_row.controls = _make_tabs(idx)
            sub_container.content = panels[idx]
            self.page.update()

        return ft.Column(
            [
                # Header row
                ft.Row([
                    ft.Column([
                        ft.Text(title, size=22, weight=ft.FontWeight.BOLD,
                                 max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(
                            f"Recorded: {(rec.get('recorded_at') or '')[:16]}"
                            f"  \u00b7  Duration: {format_seconds(rec.get('duration', 0))}",
                            size=12, color=ft.Colors.GREY_500,
                        ),
                    ], expand=True, spacing=2),
                    ft.FilledButton(
                        "PDF", icon=ft.Icons.PICTURE_AS_PDF,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.RED_700,
                                              color=ft.Colors.WHITE),
                        on_click=lambda e: self._export_pdf(self.selected_recording_id),
                    ),
                    ft.FilledButton(
                        "PPTX", icon=ft.Icons.SLIDESHOW,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.AMBER_700,
                                              color=ft.Colors.WHITE),
                        on_click=lambda e: self._export_pptx(self.selected_recording_id),
                    ),
                ], spacing=10),
                ft.Divider(color=ft.Colors.GREY_800, height=20),
                tab_row,
                ft.Container(height=10),
                sub_container,
            ],
            expand=True,
        )

    def _build_exec_panel(self, summary: dict) -> ft.Control:
        takeaways = [
            ft.Row([
                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE,
                         color=ft.Colors.GREEN_400, size=16),
                ft.Text(tk, size=14, color=ft.Colors.GREY_200, expand=True),
            ], spacing=8)
            for tk in (summary.get("key_takeaways") or [])
        ] or [ft.Text("None identified.", color=ft.Colors.GREY_600)]

        actions = [
            ft.Row([
                ft.Icon(ft.Icons.TASK_ALT, color=ft.Colors.INDIGO_400, size=16),
                ft.Text(act, size=14, color=ft.Colors.GREY_200, expand=True),
            ], spacing=8)
            for act in (summary.get("action_items") or [])
        ] or [ft.Text("None identified.", color=ft.Colors.GREY_600)]

        return ft.Column(
            [
                ft.Card(
                    content=ft.Container(
                        padding=20,
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(ft.Icons.LIGHTBULB_OUTLINE,
                                         color=ft.Colors.AMBER_400, size=18),
                                ft.Text("Executive Overview",
                                         size=14, weight=ft.FontWeight.BOLD,
                                         color=ft.Colors.INDIGO_300),
                            ], spacing=8),
                            ft.Container(height=8),
                            ft.Text(
                                summary.get("executive_summary") or "No summary generated.",
                                size=14, color=ft.Colors.GREY_200,
                            ),
                        ]),
                    ),
                    elevation=2,
                ),
                ft.Container(height=12),
                ft.Text("Key Takeaways", size=14, weight=ft.FontWeight.BOLD,
                         color=ft.Colors.GREEN_400),
                ft.Column(takeaways, spacing=6),
                ft.Container(height=14),
                ft.Text("Action Items", size=14, weight=ft.FontWeight.BOLD,
                         color=ft.Colors.INDIGO_400),
                ft.Column(actions, spacing=6),
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=4,
        )

    def _build_topics_panel(self, summary: dict) -> ft.Control:
        topics = summary.get("topics") or []
        if not topics:
            return ft.Text("No topics available.", color=ft.Colors.GREY_600)

        cards = []
        for top in topics:
            cards.append(
                ft.Card(
                    content=ft.Container(
                        padding=14,
                        content=ft.Column([
                            ft.Row([
                                ft.Container(
                                    content=ft.Text(
                                        top.get("timestamp", "[00:00]"),
                                        size=11, weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.WHITE,
                                    ),
                                    bgcolor=ft.Colors.INDIGO_600,
                                    border_radius=4,
                                    padding=ft.Padding(left=8, top=4, right=8, bottom=4),
                                ),
                                ft.Text(
                                    top.get("topic", ""),
                                    size=15, weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.WHITE,
                                ),
                            ], spacing=10),
                            ft.Container(height=4),
                            ft.Text(top.get("details", ""),
                                     size=13, color=ft.Colors.GREY_300),
                        ]),
                    ),
                    elevation=2,
                )
            )
        return ft.Column(cards, scroll=ft.ScrollMode.AUTO, spacing=6)

    def _build_transcript_panel(self, transcript: str) -> ft.Control:
        if not transcript:
            return ft.Text("No transcript available.", color=ft.Colors.GREY_600)
        return ft.Container(
            content=ft.Column([
                ft.Text(
                    transcript,
                    size=12,
                    font_family="Courier New",
                    color=ft.Colors.GREY_300,
                    selectable=True,
                )
            ], scroll=ft.ScrollMode.AUTO),
            expand=True,
        )

    # =========================================================================
    #  VIEW 4 – AI Q&A
    # =========================================================================
    def _view_qna(self) -> ft.Control:
        rec = db.get_recording(self.selected_recording_id) if self.selected_recording_id else None
        session_title = rec["title"] if rec else "No session selected"

        # Load history
        self.chat_list.controls.clear()
        if self.selected_recording_id and rec:
            for msg in db.get_chat_history(self.selected_recording_id):
                self._append_chat_bubble(msg["sender"], msg["message"])

        quick_prompts = [
            "Summarise this session in 5 bullet points.",
            "What were the main action items?",
            "Explain the key concepts discussed.",
            "What questions were raised and how were they answered?",
        ]

        return ft.Column(
            [
                ft.Row([
                    ft.Icon(ft.Icons.SMART_TOY, color=ft.Colors.INDIGO_400, size=26),
                    ft.Column([
                        ft.Text("AI Training Assistant", size=22,
                                 weight=ft.FontWeight.BOLD),
                        ft.Text(f"Session: {session_title}",
                                 size=12, color=ft.Colors.GREY_500,
                                 max_lines=1,
                                 overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=2, expand=True),
                ], spacing=10),
                ft.Divider(color=ft.Colors.GREY_800, height=20),

                # Quick prompts
                ft.Row(
                    [
                        ft.OutlinedButton(
                            qp,
                            style=ft.ButtonStyle(padding=ft.Padding(left=10, top=6, right=10, bottom=6)),
                            on_click=lambda e, q=qp: self._send_quick(q),
                        )
                        for qp in quick_prompts
                    ],
                    scroll=ft.ScrollMode.AUTO,
                    spacing=8,
                ),
                ft.Container(height=8),

                # Chat history
                ft.Container(
                    content=self.chat_list,
                    border=ft.Border.all(1, ft.Colors.GREY_800),
                    border_radius=8,
                    bgcolor=ft.Colors.GREY_900,
                    expand=True,
                ),
                ft.Container(height=8),

                # Input row
                ft.Row([
                    self.txt_question,
                    self.btn_send,
                ], spacing=6),
            ],
            expand=True,
        )

    def _send_quick(self, text: str):
        self.txt_question.value = text
        self._on_send_chat(None)

    def _on_send_chat(self, e):
        question = (self.txt_question.value or "").strip()
        if not question:
            return
        if not self.selected_recording_id:
            self.toast("Select a session first (Library tab).", ft.Colors.AMBER_700)
            return

        self.txt_question.value = ""
        self._append_chat_bubble("You", question)
        db.save_chat_message(self.selected_recording_id, "User", question)
        self.page.update()

        def _compute():
            try:
                rec        = db.get_recording(self.selected_recording_id) or {}
                transcript = rec.get("transcript", "")
                summary    = rec.get("summary", {}) or {}
                history    = db.get_chat_history(self.selected_recording_id)
                answer     = self.ai_engine.answer_question(
                    transcript, summary, question, history
                )
                self._append_chat_bubble("TrainIQ AI", answer)
                db.save_chat_message(self.selected_recording_id, "TrainIQ AI", answer)
                self.page.update()
            except RuntimeError:
                pass  # Session destroyed (window closed)
            except Exception as ex:
                print(f"[_compute] {ex}")


        threading.Thread(target=_compute, daemon=True).start()

    def _append_chat_bubble(self, sender: str, message: str):
        is_user = (sender == "You")
        bubble = ft.Container(
            content=ft.Column([
                ft.Text(
                    sender,
                    size=11,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.INDIGO_300 if is_user else ft.Colors.GREEN_400,
                ),
                ft.Text(message, size=13, color=ft.Colors.GREY_100, selectable=True),
            ], spacing=4),
            bgcolor=ft.Colors.INDIGO_900 if is_user else ft.Colors.GREY_800,
            border_radius=ft.BorderRadius(
                top_left=12, top_right=12,
                bottom_left=0 if is_user else 12,
                bottom_right=12 if is_user else 0,
            ),
            padding=ft.Padding(left=12, top=12, right=12, bottom=12),
            margin=ft.Margin(
                left=80 if is_user else 0,
                right=0 if is_user else 80,
            ),
        )
        self.chat_list.controls.append(bubble)

    # =========================================================================
    #  VIEW 5 – SETTINGS
    # =========================================================================
    def _view_settings(self) -> ft.Control:
        return ft.Column(
            [
                ft.Row([
                    ft.Icon(ft.Icons.SETTINGS, color=ft.Colors.INDIGO_400, size=26),
                    ft.Text("Settings", size=22, weight=ft.FontWeight.BOLD),
                ], spacing=10),
                ft.Divider(color=ft.Colors.GREY_800, height=24),

                # Gemini API Key card
                ft.Card(
                    content=ft.Container(
                        padding=20,
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(ft.Icons.CLOUD, color=ft.Colors.BLUE_400, size=20),
                                ft.Text("Google Gemini AI Configuration",
                                         size=14, weight=ft.FontWeight.BOLD,
                                         color=ft.Colors.INDIGO_300),
                            ], spacing=8),
                            ft.Container(height=6),
                            ft.Text(
                                "Add your Gemini API key to enable multimodal "
                                "audio/video transcription, deep AI summaries, "
                                "and intelligent Q&A reasoning.",
                                size=12, color=ft.Colors.GREY_500,
                            ),
                            ft.Container(height=12),
                            ft.Row([self.txt_api_key]),
                            ft.Container(height=12),
                            ft.Row([
                                ft.FilledButton(
                                    "Save API Key",
                                    icon=ft.Icons.SAVE,
                                    on_click=self._on_save_settings,
                                ),
                                ft.TextButton(
                                    "Get API Key (Google AI Studio)",
                                    icon=ft.Icons.OPEN_IN_NEW,
                                    on_click=lambda e: open_file_os(
                                        "https://aistudio.google.com/app/apikey"
                                    ),
                                ),
                            ], spacing=12),
                        ]),
                    ),
                    elevation=2,
                ),

                ft.Container(height=20),

                # About card
                ft.Card(
                    content=ft.Container(
                        padding=20,
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(ft.Icons.INFO_OUTLINE,
                                         color=ft.Colors.INDIGO_300, size=18),
                                ft.Text("About TrainIQ",
                                         size=14, weight=ft.FontWeight.BOLD,
                                         color=ft.Colors.INDIGO_300),
                            ], spacing=8),
                            ft.Container(height=8),
                            ft.Text("Version 1.0.0 – Enterprise Edition",
                                     size=13, color=ft.Colors.WHITE),
                            ft.Text(
                                "Built for Druidot Consulting Private Limited "
                                "– Python Development Internship",
                                size=12, color=ft.Colors.GREY_400,
                            ),
                            ft.Container(height=8),
                            ft.Text(
                                "Stack: Python · Flet · OpenCV · sounddevice · "
                                "Google Gemini AI · ReportLab · python-pptx · SQLite",
                                size=11, color=ft.Colors.GREY_600,
                            ),
                            ft.Container(height=8),
                            ft.Text(
                                "Features: Screen + Audio Recording · AI Transcription · "
                                "Smart Summarisation · Interactive Q&A · PDF Export · "
                                "PowerPoint Generation · Persistent Session Library",
                                size=11, color=ft.Colors.GREY_600,
                            ),
                        ]),
                    ),
                    elevation=2,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    def _on_save_settings(self, e):
        key = self.txt_api_key.value.strip()
        db.set_setting("gemini_api_key", key)
        self.transcriber.set_api_key(key)
        self.ai_engine.set_api_key(key)
        self.toast("✅ API Key saved!", ft.Colors.GREEN_700)

    # =========================================================================
    #  HELPERS
    # =========================================================================
    def _switch_to(self, index: int):
        self.nav_rail.selected_index = index
        views = [
            self._view_recorder,
            self._view_library,
            self._view_summary,
            self._view_qna,
            self._view_settings,
        ]
        self.body.content = views[index]()
        self.page.update()


# ─────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def main(page: ft.Page):
    TrainIQApp(page)


if __name__ == "__main__":
    port_env = os.environ.get("PORT")
    if port_env:
        port = int(port_env)
        if hasattr(ft, "app"):
            ft.app(target=main, port=port, view=ft.AppView.WEB_BROWSER)
        else:
            ft.run(main, port=port)
    else:
        if hasattr(ft, "app"):
            ft.app(target=main)
        else:
            ft.run(main)

import sqlite3
import os
import json
from typing import List, Dict, Any, Optional

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trainiq.db")

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes database tables if they do not exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Speed & Concurrency Pragmas
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    
    # Recordings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recordings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            file_path TEXT NOT NULL,
            duration REAL DEFAULT 0,
            file_size INTEGER DEFAULT 0,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            transcript TEXT,
            summary_json TEXT,
            status TEXT DEFAULT 'ready'
        )
    """)
    
    # Chat History Table for Q&A
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qna_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recording_id INTEGER NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp_ref TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (recording_id) REFERENCES recordings(id) ON DELETE CASCADE
        )
    """)
    
    # App Settings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qna_rec_id ON qna_history(recording_id);")
    
    conn.commit()
    conn.close()

def save_recording(title: str, file_path: str, duration: float, file_size: int, transcript: str = "", summary: dict = None) -> int:
    """Saves a new recording record and returns its ID."""
    conn = get_connection()
    cursor = conn.cursor()
    summary_json = json.dumps(summary) if summary else ""
    cursor.execute("""
        INSERT INTO recordings (title, file_path, duration, file_size, transcript, summary_json)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (title, file_path, duration, file_size, transcript, summary_json))
    rec_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return rec_id

def update_recording(recording_id: int, transcript: str = None, summary: dict = None, title: str = None):
    """Updates transcript, summary or title for a recording."""
    conn = get_connection()
    cursor = conn.cursor()
    if transcript is not None:
        cursor.execute("UPDATE recordings SET transcript = ? WHERE id = ?", (transcript, recording_id))
    if summary is not None:
        cursor.execute("UPDATE recordings SET summary_json = ? WHERE id = ?", (json.dumps(summary), recording_id))
    if title is not None:
        cursor.execute("UPDATE recordings SET title = ? WHERE id = ?", (title, recording_id))
    conn.commit()
    conn.close()

def get_recordings() -> List[Dict[str, Any]]:
    """Fetches all recording records ordered by recency."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM recordings ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    result = []
    for r in rows:
        item = dict(r)
        if item.get("summary_json"):
            try:
                item["summary"] = json.loads(item["summary_json"])
            except Exception:
                item["summary"] = {}
        else:
            item["summary"] = {}
        result.append(item)
    return result

def get_recording(recording_id: int) -> Optional[Dict[str, Any]]:
    """Fetches a single recording by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM recordings WHERE id = ?", (recording_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    item = dict(row)
    if item.get("summary_json"):
        try:
            item["summary"] = json.loads(item["summary_json"])
        except Exception:
            item["summary"] = {}
    else:
        item["summary"] = {}
    return item

def delete_recording(recording_id: int):
    """Deletes a recording and its Q&A history."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM recordings WHERE id = ?", (recording_id,))
    cursor.execute("DELETE FROM qna_history WHERE recording_id = ?", (recording_id,))
    conn.commit()
    conn.close()

def save_chat_message(recording_id: int, sender: str, message: str, timestamp_ref: str = ""):
    """Saves a Q&A chat message."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO qna_history (recording_id, sender, message, timestamp_ref)
        VALUES (?, ?, ?, ?)
    """, (recording_id, sender, message, timestamp_ref))
    conn.commit()
    conn.close()

def get_chat_history(recording_id: int) -> List[Dict[str, Any]]:
    """Gets Q&A history for a recording."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM qna_history WHERE recording_id = ? ORDER BY id ASC", (recording_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def set_setting(key: str, value: str):
    """Saves a setting key-value pair."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_setting(key: str, default: str = "") -> str:
    """Gets a setting value by key."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, List
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "core_memory.db"))


def ensure_tables_exist():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Table: Codex Rules
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS codex (
            id INTEGER PRIMARY KEY,
            section TEXT NOT NULL,
            rules TEXT NOT NULL
        )
    """
    )

    # Table: Known Symbolic Tokens
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS known_tokens (
            id INTEGER PRIMARY KEY,
            label TEXT NOT NULL,
            tokens TEXT NOT NULL
        )
    """
    )

    # Table: Symbolic Reflection Memory Log
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            input TEXT,
            reflection TEXT
        )
    """
    )

    conn.commit()
    conn.close()


def load_codex_rules() -> Dict[str, Any]:
    ensure_tables_exist()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT section, rules FROM codex")
    results = cursor.fetchall()
    conn.close()

    return {section: json.loads(rules) for section, rules in results}


def get_known_tokens() -> Dict[str, list]:
    ensure_tables_exist()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT label, tokens FROM known_tokens")
    results = cursor.fetchall()
    conn.close()

    return {label: json.loads(tokens) for label, tokens in results}


def update_memory_state(db_path: str, symbolic_input: dict, reflection_result: Any):
    ensure_tables_exist()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    timestamp = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO memory_log (timestamp, input, reflection)
        VALUES (?, ?, ?)
    """,
        (
            timestamp,
            json.dumps(symbolic_input, indent=2),
            (
                reflection_result
                if isinstance(reflection_result, str)
                else json.dumps(reflection_result, indent=2)
            ),
        ),
    )

    conn.commit()
    conn.close()


def load_memory_state() -> List[Dict[str, Any]]:
    ensure_tables_exist()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT timestamp, input FROM memory_log ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    return [{"timestamp": ts, "input": inp} for ts, inp in rows]

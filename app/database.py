import sqlite3
from flask import current_app


def get_db():
    db = sqlite3.connect(current_app.config["DATABASE_URL"])
    db.row_factory = sqlite3.Row
    return db


def init_db(app):
    with app.app_context():
        db = get_db()
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT,
                position TEXT,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.commit()
        db.close()


def add_candidate(name, email, phone="", position="", message=""):
    db = get_db()
    db.execute(
        "INSERT INTO candidates (name, email, phone, position, message) VALUES (?, ?, ?, ?, ?)",
        (name, email, phone, position, message),
    )
    db.commit()
    db.close()


def list_candidates():
    db = get_db()
    rows = db.execute("SELECT * FROM candidates ORDER BY created_at DESC").fetchall()
    db.close()
    return [dict(r) for r in rows]

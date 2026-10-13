import sqlite3

def get_db():
    db = sqlite3.connect('database.db')
    db.row_factory = sqlite3.Row
    return db

def init_db(app):
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL
            )
        ''')
        db.commit()
        db.close()
import sqlite3
import os

class KnowledgeBase:
    def __init__(self):
        # Use APPDATA for user-writable files
        self.data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), "StealthHUD")
        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, "brain.db")
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Identity table for personal facts
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS identity (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        # Experience table for roles and history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS experience (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT,
                role TEXT,
                duration TEXT,
                description TEXT,
                is_current INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()

    def add_identity(self, key, value):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO identity (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        conn.close()

    def add_experience(self, company, role, duration, description, is_current=0):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO experience (company, role, duration, description, is_current) 
            VALUES (?, ?, ?, ?, ?)
        """, (company, role, duration, description, is_current))
        conn.commit()
        conn.close()

    def clear_brain(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM identity")
        cursor.execute("DELETE FROM experience")
        conn.commit()
        conn.close()

    def query_identity(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM identity")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def query_brain(self, query_type="all"):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if query_type == "current":
            cursor.execute("SELECT * FROM experience WHERE is_current = 1")
        else:
            cursor.execute("SELECT * FROM experience ORDER BY id DESC")
            
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

kb = KnowledgeBase()

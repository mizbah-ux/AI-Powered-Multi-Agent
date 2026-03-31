import sqlite3

DB_PATH = "agent_system.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_input TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            agent_name TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            agent_name TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

def create_task(user_input: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (user_input) VALUES (?)", (user_input,))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

def update_task_status(task_id: int, status: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
    conn.commit()
    conn.close()

def add_log(task_id: int, agent_name: str, message: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO logs (task_id, agent_name, message) VALUES (?, ?, ?)",
        (task_id, agent_name, message)
    )
    conn.commit()
    conn.close()

def get_logs(task_id: int) -> list:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT agent_name, message, created_at FROM logs WHERE task_id = ? ORDER BY id ASC",
        (task_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"agent": r[0], "message": r[1], "time": r[2]} for r in rows]

def get_all_tasks() -> list:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_input, status, created_at FROM tasks ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "input": r[1], "status": r[2], "created_at": r[3]} for r in rows]

def add_memory(task_id: int, agent_name: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO memory (task_id, agent_name, content) VALUES (?, ?, ?)",
        (task_id, agent_name, content)
    )
    conn.commit()
    conn.close()


def get_memory(task_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT agent_name, content FROM memory WHERE task_id = ? ORDER BY id ASC",
        (task_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"agent": r[0], "content": r[1]} for r in rows]
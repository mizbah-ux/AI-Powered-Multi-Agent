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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS global_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_input TEXT NOT NULL,
            plan TEXT NOT NULL,
            result TEXT NOT NULL,
            analysis TEXT NOT NULL,
            score INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback_learning (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_input TEXT NOT NULL,
            failed_plan TEXT NOT NULL,
            improved_plan TEXT,
            feedback TEXT NOT NULL,
            score INTEGER NOT NULL,
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
    conn.commit()  # Ensure immediate commit
    conn.close()
    # Debug: print to console for immediate visibility
    print(f"[LOG] Task {task_id} - {agent_name}: {message}")

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


def get_analytics() -> dict:
    """Get system performance analytics."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get task counts by status
    cursor.execute("""
        SELECT status, COUNT(*) as count 
        FROM tasks 
        GROUP BY status
    """)
    status_counts = dict(cursor.fetchall())
    
    total_tasks = sum(status_counts.values())
    completed_tasks = status_counts.get('completed', 0)
    failed_tasks = status_counts.get('failed', 0)
    
    # Calculate success rate
    success_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Get average score from completed tasks
    cursor.execute("""
        SELECT content FROM memory m
        JOIN tasks t ON m.task_id = t.id
        WHERE t.status = 'completed' AND m.agent_name = 'Analyst'
    """)
    analysis_results = cursor.fetchall()
    
    scores = []
    for (content,) in analysis_results:
        import re
        score_match = re.search(r'Score:\s*(\d+)', content)
        if score_match:
            scores.append(int(score_match.group(1)))
    
    avg_score = sum(scores) / len(scores) if scores else 0
    
    conn.close()
    
    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "failed_tasks": failed_tasks,
        "success_rate": round(success_rate, 2),
        "avg_score": round(avg_score, 2)
    }


def store_global_memory(task_input: str, plan: str, result: str, analysis: str, score: int) -> int:
    """Store successful task execution in global memory for future learning."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO global_memory (task_input, plan, result, analysis, score) 
           VALUES (?, ?, ?, ?, ?)""",
        (task_input, plan, result, analysis, score)
    )
    memory_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return memory_id


def get_similar_tasks(user_input: str, limit: int = 2) -> list:
    """Search global memory for similar tasks using LIKE matching."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Extract keywords from user input for better matching
    keywords = user_input.lower().split()
    like_conditions = []
    params = []
    
    # Create LIKE conditions for each keyword
    for keyword in keywords[:5]:  # Limit to first 5 keywords to avoid too complex query
        if len(keyword) > 2:  # Skip very short words
            like_conditions.append("LOWER(task_input) LIKE ?")
            params.append(f"%{keyword}%")
    
    if not like_conditions:
        return []
    
    # Build the query
    query = f"""
        SELECT task_input, plan, result, analysis, score, created_at
        FROM global_memory 
        WHERE {' AND '.join(like_conditions)}
        ORDER BY score DESC, created_at DESC
        LIMIT ?
    """
    params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "task_input": r[0],
            "plan": r[1], 
            "result": r[2],
            "analysis": r[3],
            "score": r[4],
            "created_at": r[5]
        }
        for r in rows
    ]


def store_feedback_learning(task_input: str, failed_plan: str, feedback: str, score: int) -> int:
    """Store initial failed attempt for learning."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO feedback_learning (task_input, failed_plan, feedback, score) 
           VALUES (?, ?, ?, ?)""",
        (task_input, failed_plan, feedback, score)
    )
    learning_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return learning_id


def update_improved_plan(learning_id: int, improved_plan: str):
    """Update the improved plan after successful retry."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE feedback_learning SET improved_plan = ? WHERE id = ?",
        (improved_plan, learning_id)
    )
    conn.commit()
    conn.close()


def get_similar_feedback(user_input: str, limit: int = 3) -> list:
    """Get past feedback for similar tasks."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Extract keywords for matching
    keywords = user_input.lower().split()
    like_conditions = []
    params = []
    
    for keyword in keywords[:5]:
        if len(keyword) > 2:
            like_conditions.append("LOWER(task_input) LIKE ?")
            params.append(f"%{keyword}%")
    
    if not like_conditions:
        return []
    
    query = f"""
        SELECT task_input, failed_plan, improved_plan, feedback, score, created_at
        FROM feedback_learning 
        WHERE {' AND '.join(like_conditions)} AND improved_plan IS NOT NULL
        ORDER BY score DESC, created_at DESC
        LIMIT ?
    """
    params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "task_input": r[0],
            "failed_plan": r[1],
            "improved_plan": r[2],
            "feedback": r[3],
            "score": r[4],
            "created_at": r[5]
        }
        for r in rows
    ]
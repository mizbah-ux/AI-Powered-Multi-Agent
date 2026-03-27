from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from database import init_db, create_task, update_task_status, get_logs, get_all_tasks
from agents import PlannerAgent, SupervisorAgent, ExecutorAgent, AnalystAgent

app = FastAPI(title="Multi-Agent System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB on startup
init_db()

class TaskRequest(BaseModel):
    user_input: str

@app.post("/task")
def run_task(request: TaskRequest):
    """Main endpoint: runs the full 4-agent pipeline."""
    user_input = request.user_input
    
    # 1. Save task to DB
    task_id = create_task(user_input)
    update_task_status(task_id, "running")
    
    try:
        # 2. Planner breaks it down
        planner = PlannerAgent()
        steps = planner.run(task_id, user_input)
        
        # 3. Supervisor approves
        supervisor = SupervisorAgent()
        approved = supervisor.approve_plan(task_id, steps)
        
        if not approved:
            update_task_status(task_id, "failed")
            return {"task_id": task_id, "status": "failed", "reason": "Plan rejected"}
        
        # 4. Executor runs the steps
        executor = ExecutorAgent()
        result = executor.run(task_id, steps, user_input)
        
        # 5. Analyst validates
        analyst = AnalystAgent()
        analysis = analyst.run(task_id, user_input, result)
        
        # 6. Supervisor finalizes
        supervisor.finalize(task_id, analysis)
        update_task_status(task_id, "completed")
        
        return {
            "task_id": task_id,
            "status": "completed",
            "result": result,
            "analysis": analysis
        }
    
    except Exception as e:
        update_task_status(task_id, "failed")
        return {"task_id": task_id, "status": "failed", "error": str(e)}

@app.get("/task/{task_id}/logs")
def get_task_logs(task_id: int):
    """Returns all agent activity logs for a task."""
    return {"task_id": task_id, "logs": get_logs(task_id)}

@app.get("/tasks")
def list_tasks():
    """Returns all tasks ever submitted."""
    return {"tasks": get_all_tasks()}

@app.get("/")
def health_check():
    return {"status": "running", "message": "Multi-Agent System is live"}

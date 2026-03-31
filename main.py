from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import re
import os

load_dotenv()

from database import init_db, create_task, update_task_status, get_logs, get_all_tasks, add_log, add_memory, store_global_memory, get_analytics, store_feedback_learning, update_improved_plan
from agents import PlannerAgent, SupervisorAgent, ExecutorAgent, AnalystAgent, improve_plan

app = FastAPI(title="Multi-Agent System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="."), name="static")

init_db()

# In-memory store for final results (keyed by task_id)
task_results: dict = {}


class TaskRequest(BaseModel):
    user_input: str


@app.post("/task")
def run_task(request: TaskRequest, background_tasks: BackgroundTasks):
    """Creates task, starts pipeline in background, returns task_id immediately."""
    task_id = create_task(request.user_input)
    update_task_status(task_id, "pending")
    background_tasks.add_task(_run_pipeline, task_id, request.user_input)
    return {"task_id": task_id, "status": "started"}


@app.get("/task/{task_id}/status")
def get_task_status(task_id: int):
    """Poll this endpoint to check if pipeline is done and get the result."""
    tasks = get_all_tasks()
    for t in tasks:
        if t["id"] == task_id:
            response = {
                "task_id": task_id,
                "status": t["status"],
            }
            # Attach result once completed
            if t["status"] == "completed" and task_id in task_results:
                response["result"]   = task_results[task_id].get("result", "")
                response["analysis"] = task_results[task_id].get("analysis", "")
            elif t["status"] == "failed" and task_id in task_results:
                response["error"]  = task_results[task_id].get("error", "")
                response["reason"] = task_results[task_id].get("reason", "")
            return response
    return {"task_id": task_id, "status": "not_found"}


def _run_pipeline(task_id: int, user_input: str):
    update_task_status(task_id, "running")
    try:
        planner = PlannerAgent()
        steps = planner.run(task_id, user_input)

        supervisor = SupervisorAgent()
        approved = supervisor.approve_plan(task_id, steps)

        if not approved:
            update_task_status(task_id, "failed")
            task_results[task_id] = {"reason": "Plan rejected by Supervisor"}
            return

        max_attempts = 2
        attempt = 0
        result = ""
        analysis = ""
        learning_id = None  # Track feedback learning entry

        while attempt < max_attempts:
            executor = ExecutorAgent()
            result = executor.run(task_id, steps, user_input)

            analyst = AnalystAgent()
            analysis = analyst.run(task_id, user_input, result)

            score_match = re.search(r"Score:\s*(\d+)", analysis)
            score = int(score_match.group(1)) if score_match else 0

            if score >= 8:
                # Success - update learning if this was a retry
                if learning_id:
                    improved_plan_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
                    update_improved_plan(learning_id, improved_plan_text)
                    add_log(task_id, "SYS", f"Learning updated: Improved plan stored (Score: {score}/10)")
                break

            # Score too low - store feedback for learning if first attempt
            if attempt == 0:
                failed_plan_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
                learning_id = store_feedback_learning(user_input, failed_plan_text, analysis, score)
                add_log(task_id, "SYS", f"Feedback stored for learning (ID: {learning_id}, Score: {score}/10)")

            # Use improved plan instead of blind re-planning
            if attempt < max_attempts - 1:  # Don't improve on last attempt
                add_log(task_id, "SYS", "Improving plan based on feedback...")
                steps = improve_plan(steps, analysis)
                add_log(task_id, "SYS", f"Plan improved to {len(steps)} steps")
                
                # Get supervisor approval for improved plan
                if supervisor.approve_plan(task_id, steps):
                    add_log(task_id, "SYS", "Improved plan approved")
                else:
                    add_log(task_id, "SYS", "Improved plan rejected, proceeding with original")
            
            attempt += 1

        add_memory(task_id, "FinalResult", result)
        add_memory(task_id, "Analysis", analysis)

        supervisor.finalize(task_id, analysis)
        update_task_status(task_id, "completed")
        add_log(task_id, "SYS", f"Pipeline complete. Result length: {len(result)}")

        # Store result so /task/{id}/status can return it
        task_results[task_id] = {"result": result, "analysis": analysis}

        # 🧠 Store in global memory if score >= 8
        if score >= 8:
            try:
                plan_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
                memory_id = store_global_memory(
                    task_input=user_input,
                    plan=plan_text,
                    result=result,
                    analysis=analysis,
                    score=score
                )
                add_log(task_id, "SYS", f"Stored in global memory (ID: {memory_id}, Score: {score}/10)")
            except Exception as e:
                add_log(task_id, "SYS", f"Failed to store in global memory: {str(e)}")
        else:
            add_log(task_id, "SYS", f"Score {score}/10 too low for global memory storage")

    except Exception as e:
        update_task_status(task_id, "failed")
        task_results[task_id] = {"error": str(e)}
        add_log(task_id, "SYS", f"Pipeline error: {str(e)}")


@app.get("/task/{task_id}/logs")
def get_task_logs(task_id: int):
    return {"task_id": task_id, "logs": get_logs(task_id)}


@app.get("/tasks")
def list_tasks():
    return {"tasks": get_all_tasks()}


@app.get("/analytics")
def get_system_analytics():
    """Get system performance analytics."""
    try:
        analytics = get_analytics()
        return {
            "total_tasks": analytics["total_tasks"],
            "success_rate": analytics["success_rate"],
            "avg_score": analytics["avg_score"]
        }
    except Exception as e:
        return {"error": str(e), "total_tasks": 0, "success_rate": 0, "avg_score": 0}


@app.get("/")
def health_check():
    return {"status": "running", "message": "Multi-Agent System is live"}


@app.get("/index.html")
def serve_index():
    from fastapi.responses import FileResponse
    return FileResponse("index.html")
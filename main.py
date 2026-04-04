from fastapi import FastAPI, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import re
import os
import uuid
import pandas as pd
import json
from datetime import datetime

load_dotenv()

from database import init_db, create_task, update_task_status, get_logs, get_all_tasks, add_log, add_memory, store_global_memory, get_analytics, store_feedback_learning, update_improved_plan
from agents import PlannerAgent, SupervisorAgent, DataCleanerAgent, ExecutorAgent, AnalystAgent, improve_plan, refine_plan_with_feedback

app = FastAPI(title="Multi-Agent System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="."), name="static")
app.mount("/static/frontend", StaticFiles(directory="frontend"), name="frontend")

init_db()

# In-memory store for final results (keyed by task_id)
task_results: dict = {}

# In-memory store for uploaded files (keyed by file_id)
uploaded_files: dict = {}


class TaskRequest(BaseModel):
    user_input: str
    file_id: str = None


@app.post("/task")
def run_task(request: TaskRequest, background_tasks: BackgroundTasks):
    """Creates task, starts pipeline in background, returns task_id immediately."""
    task_id = create_task(request.user_input)
    update_task_status(task_id, "pending")
    background_tasks.add_task(_run_pipeline, task_id, request.user_input, request.file_id)
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
def generate_final_report(result, analysis):
    from agents import call_llm

    system_prompt = """
    You are a Senior Strategy Consultant at a top-tier firm (McKinsey/Bain/BCG).

    Your job is to transform raw execution data into an EXECUTIVE-LEVEL REPORT.

    STRICT FORMAT:

    📊 EXECUTIVE SUMMARY
    - 3–4 bullet points
    - Focus on decision-level insights

    🔍 KEY FINDINGS
    - Critical observations
    - Data-backed points

    📈 ANALYSIS
    - Explain trends, comparisons, reasoning

    ⚠️ RISKS & LIMITATIONS
    - Data gaps
    - Uncertainty
    - Assumptions

    💡 STRATEGIC RECOMMENDATIONS
    - Actionable steps
    - Business-focused

    🧾 FINAL VERDICT
    - Clear decision or conclusion

    STYLE:
    - Concise
    - Professional
    - No fluff
    - No casual language
    """

    try:
        return call_llm(system_prompt, f"""
    Execution Data:
    {result[:2000]}

    Analyst Notes:
    {analysis[:1000]}
    """)
    except Exception as e:
        return f"📊 EXECUTIVE SUMMARY\n- Report generation encountered an issue\n\n🔍 KEY FINDINGS\n- Analysis completed with fallback\n\n📈 ANALYSIS\n- {str(e)[:200]}\n\n💡 STRATEGIC RECOMMENDATIONS\n- Review raw data and logs for details"


def prepare_data_for_llm(file_data: dict) -> str:
    try:
        df = pd.DataFrame(file_data['data'])
        if df.empty:
            return f"File: {file_data.get('filename', 'unknown')} | No data rows"
        
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(exclude=['number']).columns.tolist()

        numeric_summary = {}
        for col in numeric_cols:
            try:
                numeric_summary[col] = {
                    "min": round(float(df[col].min()), 2),
                    "max": round(float(df[col].max()), 2),
                    "mean": round(float(df[col].mean()), 2),
                    "median": round(float(df[col].median()), 2),
                    "std": round(float(df[col].std()), 2)
                }
            except Exception as e:
                numeric_summary[col] = {"error": str(e)}

        categorical_summary = {}
        for col in categorical_cols[:5]:
            try:
                categorical_summary[col] = df[col].value_counts().head(5).to_dict()
            except Exception as e:
                categorical_summary[col] = {"error": str(e)}

        return f"""
    File: {file_data.get('filename', 'unknown')} | Total rows: {len(df)}
    Columns: {', '.join(file_data.get('columns', []))}
    Numeric Summary: {json.dumps(numeric_summary)}
    Categorical Breakdown: {json.dumps(categorical_summary)}
    """
    except Exception as e:
        return f"File: {file_data.get('filename', 'unknown')} | Error preparing data: {str(e)}"


def _run_pipeline(task_id: int, user_input: str, file_id: str = None):
    update_task_status(task_id, "running")
    
    # Get uploaded file data if available
    file_data = None
    if file_id and file_id in uploaded_files:
        file_data = uploaded_files[file_id]
        add_log(task_id, "SYS", f"Using uploaded file: {file_data['filename']} with {len(file_data['data'])} rows")
    
    try:
        planner = PlannerAgent()
        supervisor = SupervisorAgent()
        
        max_attempts = 2
        attempt = 0
        steps = []
        approved = False
        feedback = ""
        
        # Supervisor approval retry loop
        while attempt < max_attempts:
            if attempt == 0:
                # Inject file context into planner if available
                planner_input = user_input
                if file_data:
                    planner_input = f"""
                    User request: {user_input}
                    
                    User has uploaded data with columns: {', '.join(file_data['columns'])}
                    Data context for planning:
                    {prepare_data_for_llm(file_data)}
                    """
                
                steps = planner.run(task_id, planner_input)
                add_log(task_id, "SYS", f"Generated initial plan with {len(steps)} steps")
                
                # Fallback if planner returns empty steps
                if not steps or len(steps) == 0:
                    add_log(task_id, "SYS", "Warning: Planner returned no steps, using default plan")
                    steps = ["Analyze the request", "Generate insights", "Create summary"]
            else:
                add_log(task_id, "SYS", f"Plan rejected, refining...")
                add_log(task_id, "SYS", f"Retry attempt {attempt}")
                steps = refine_plan_with_feedback(steps, feedback)
                add_log(task_id, "SYS", f"Improved plan generated with {len(steps)} steps")
                
                if not steps or len(steps) == 0:
                    add_log(task_id, "SYS", "Warning: Refinement returned no steps, using default plan")
                    steps = ["Analyze the request", "Generate insights", "Create summary"]
            
            approved, feedback = supervisor.approve_plan(task_id, steps)
            
            if approved:
                add_log(task_id, "SYS", "Plan approved by Supervisor")
                break
            else:
                add_log(task_id, "SYS", f"Plan rejected: {feedback}")
                if attempt == max_attempts - 1:
                    update_task_status(task_id, "failed")
                    task_results[task_id] = {"reason": f"Plan rejected after {max_attempts} attempts. Final feedback: {feedback}"}
                    return
            
            attempt += 1

        # Continue with execution (existing logic)
        max_execution_attempts = 2
        execution_attempt = 0
        result = ""
        analysis = ""
        learning_id = None  # Track feedback learning entry
        score = 0  # Initialize score before the while loop

        if file_data is not None:
            add_log(task_id, "SYS", "Running DataCleanerAgent on uploaded file")
            cleaner = DataCleanerAgent()
            file_data = cleaner.run(task_id, file_data)

        while execution_attempt < max_execution_attempts:
            executor = ExecutorAgent()
            
            # Inject file data into executor context if available
            executor_input = user_input
            if file_data:
                executor_input = f"""
                User request: {user_input}
                
                Complete uploaded dataset context:
                {prepare_data_for_llm(file_data)}
                
                Use this data for generating visualizations and analysis.
                """
            
            result = executor.run(task_id, steps, executor_input)

            analyst = AnalystAgent()
            
            # Inject file summary into analyst context if available
            analyst_input = user_input
            if file_data:
                analyst_input = f"""
                User request: {user_input}
                
                Analysis based on uploaded file: {file_data['filename']}
                Data context for analysis:
                {prepare_data_for_llm(file_data)}
                """
            
            analysis = analyst.run(task_id, analyst_input, result)

            score_match = re.search(r"Score:\s*(\d+)", analysis)
            score = int(score_match.group(1)) if score_match else 7

            if score >= 8:
                # Success - update learning if this was a retry
                if learning_id:
                    improved_plan_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
                    update_improved_plan(learning_id, improved_plan_text)
                    add_log(task_id, "SYS", f"Learning updated: Improved plan stored (Score: {score}/10)")
                break

            # Score too low - store feedback for learning if first attempt
            if execution_attempt == 0:
                failed_plan_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
                learning_id = store_feedback_learning(user_input, failed_plan_text, analysis, score)
                add_log(task_id, "SYS", f"Feedback stored for learning (ID: {learning_id}, Score: {score}/10)")

            # Use improved plan instead of blind re-planning
            if execution_attempt < max_execution_attempts - 1:  # Don't improve on last attempt
                add_log(task_id, "SYS", "Improving plan based on feedback...")
                steps = improve_plan(steps, analysis)
                add_log(task_id, "SYS", f"Plan improved to {len(steps)} steps")
                
                # Get supervisor approval for improved plan
                approved, feedback = supervisor.approve_plan(task_id, steps)
                if approved:
                    add_log(task_id, "SYS", "Improved plan approved")
                else:
                    add_log(task_id, "SYS", "Improved plan rejected, proceeding with original")
            
            execution_attempt += 1

        try:
            final_report = generate_final_report(result, analysis)
        except Exception as e:
            add_log(task_id, "SYS", f"Final report generation failed: {str(e)}")
            final_report = f"Analysis completed. Raw result length: {len(result)} chars. Error: {str(e)[:100]}"

        add_memory(task_id, "FinalResult", final_report)
        add_memory(task_id, "Analysis", analysis)

        supervisor.finalize(task_id, analysis)
        update_task_status(task_id, "completed")
        add_log(task_id, "SYS", f"Pipeline complete. Result length: {len(result)}")

        # Store result so /task/{id}/status can return it
        task_results[task_id] = {"result": final_report, "analysis": analysis}

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


@app.get("/task/{task_id}/debug")
def get_task_debug(task_id: int):
    """Debug endpoint to check log count and timing."""
    try:
        logs = get_logs(task_id)
        tasks = get_all_tasks()
        task_info = next((t for t in tasks if t["id"] == task_id), None)
        
        return {
            "task_id": task_id,
            "task_status": task_info["status"] if task_info else "not_found",
            "log_count": len(logs),
            "logs": logs,
            "timestamp": str(datetime.now()) if 'datetime' in globals() else "unknown"
        }
    except Exception as e:
        return {"error": str(e), "task_id": task_id}


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


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload and parse CSV, Excel, or JSON files."""
    try:
        # Validate file type
        if not file.filename:
            return {"error": "No file provided"}
        
        file_extension = file.filename.split('.')[-1].lower()
        if file_extension not in ['csv', 'xlsx', 'json']:
            return {"error": "Unsupported file type. Please upload CSV, Excel (.xlsx), or JSON"}
        
        # Read file content
        content = await file.read()
        
        # Parse based on file type
        if file_extension == 'csv':
            df = pd.read_csv(pd.io.common.StringIO(content.decode('utf-8')))
        elif file_extension == 'xlsx':
            df = pd.read_excel(pd.io.common.BytesIO(content))
        elif file_extension == 'json':
            data = json.loads(content.decode('utf-8'))
            if isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                df = pd.DataFrame([data])
        
        # Generate file ID
        file_id = str(uuid.uuid4())
        
        # Create summary statistics
        summary = {}
        for col in df.select_dtypes(include=['number']).columns:
            summary[col] = {
                "min": float(df[col].min()),
                "max": float(df[col].max()),
                "mean": float(df[col].mean()),
                "count": int(df[col].count())
            }
        
        # Prepare preview data (first 5 rows)
        preview = df.head(5).to_dict('records')
        
        # Store file data
        uploaded_files[file_id] = {
            "filename": file.filename,
            "columns": list(df.columns),
            "data": df.to_dict('records'),
            "summary": summary,
            "preview": preview
        }
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "rows": len(df),
            "columns": list(df.columns),
            "preview": preview,
            "summary": summary
        }
        
    except Exception as e:
        return {"error": f"Failed to parse file: {str(e)}"}


@app.get("/upload/{file_id}")
def get_uploaded_file(file_id: str):
    """Retrieve uploaded file data."""
    if file_id not in uploaded_files:
        return {"error": "File not found"}
    
    return uploaded_files[file_id]


@app.get("/")
def serve_frontend():
    """Serve the frontend dashboard by default."""
    from fastapi.responses import FileResponse
    return FileResponse("frontend/index.html")

@app.get("/health")
def health_check():
    return {"status": "running", "message": "Multi-Agent System is live"}


@app.get("/index.html")
def serve_index():
    from fastapi.responses import FileResponse
    return FileResponse("frontend/index.html")
import os
from groq import Groq
from database import add_log

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

def call_llm(system_prompt: str, user_message: str) -> str:
    """Single reusable function for all LLM calls."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        max_tokens=1000
    )
    return response.choices[0].message.content


class PlannerAgent:
    def run(self, task_id: int, user_input: str) -> list:
        add_log(task_id, "Planner", f"Received request: {user_input}")
        
        system_prompt = """You are a task planner. Break the user's request into 3-5 
        clear executable steps. Return ONLY a numbered list, nothing else.
        Example format:
        1. Step one description
        2. Step two description
        3. Step three description"""
        
        result = call_llm(system_prompt, user_input)
        
        # Parse into list
        steps = []
        for line in result.strip().split('\n'):
            line = line.strip()
            if line and line[0].isdigit():
                # Remove "1. " prefix
                step = line.split('. ', 1)[-1]
                steps.append(step)
        
        add_log(task_id, "Planner", f"Created {len(steps)} tasks: {steps}")
        return steps


class SupervisorAgent:
    def approve_plan(self, task_id: int, steps: list) -> bool:
        add_log(task_id, "Supervisor", f"Reviewing plan with {len(steps)} steps")
        
        # Check plan is not empty and has reasonable steps
        if not steps or len(steps) < 2:
            add_log(task_id, "Supervisor", "Plan rejected: too few steps")
            return False
        
        add_log(task_id, "Supervisor", "Plan approved. Sending to Executor.")
        return True
    
    def finalize(self, task_id: int, analysis: str):
        add_log(task_id, "Supervisor", f"Task complete. Final verdict: {analysis[:100]}")


class ExecutorAgent:
    def run(self, task_id: int, steps: list, user_input: str) -> str:
        add_log(task_id, "Executor", "Starting execution")
        
        results = []
        for i, step in enumerate(steps, 1):
            add_log(task_id, "Executor", f"Running step {i}: {step}")
            
            system_prompt = """You are an executor. Complete the given task step 
            concisely in 2-3 sentences. Be specific and practical."""
            
            step_result = call_llm(system_prompt, f"Task context: {user_input}\nStep to execute: {step}")
            results.append(f"Step {i} ({step}): {step_result}")
            add_log(task_id, "Executor", f"Completed step {i}")
        
        combined = "\n\n".join(results)
        add_log(task_id, "Executor", "All steps completed")
        return combined


class AnalystAgent:
    def run(self, task_id: int, original_input: str, execution_result: str) -> str:
        add_log(task_id, "Analyst", "Validating execution output")
        
        system_prompt = """You are a quality analyst. Review the execution output 
        against the original request. Give a brief quality score (1-10) and 
        one sentence of feedback. Format: 'Score: X/10. Feedback: [your feedback]'"""
        
        analysis = call_llm(
            system_prompt,
            f"Original request: {original_input}\n\nExecution output: {execution_result}"
        )
        
        add_log(task_id, "Analyst", f"Analysis complete: {analysis}")
        return analysis
    
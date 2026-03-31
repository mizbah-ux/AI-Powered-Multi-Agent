import os
from groq import Groq
from database import add_log, get_memory, update_task_status
import re


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
    
        # 🧠 Fetch memory
        memory = get_memory(task_id)
        memory_text = "\n".join([m["content"] for m in memory]) if memory else ""
    
        system_prompt = """
        You are a task planner.
        
        Break the task into EXACTLY 3-5 steps.
        
        STRICT RULES:
        - Use ONLY numbered format
        - Format MUST be:
        1. Step one
        2. Step two
        3. Step three
        
        DO NOT use bullets, dashes, or explanations.
        """
    
        # 🧠 Inject memory context
        full_input = f"""
        Previous context:
        {memory_text}
    
        New request:
        {user_input}
        """
    
        result = call_llm(system_prompt, full_input)

        steps = []

        for line in result.strip().split('\n'):
            line = line.strip()

            match = re.match(r"^(\d+[\.\)]\s*|-|\•)\s*(.+)", line)

            if match:
                step = match.group(2)
                steps.append(step)
    
        add_log(task_id, "Planner", f"Created {len(steps)} tasks")
        return steps


class SupervisorAgent:
    def approve_plan(self, task_id: int, steps: list) -> bool:
        add_log(task_id, "Supervisor", f"Reviewing plan with {len(steps)} steps")

        system_prompt = """
        You are a strict supervisor.
        Evaluate if this plan is logical, complete, and actionable.

        Return ONLY:
        APPROVED
        or
        REJECTED: reason
        """

        response = call_llm(system_prompt, "\n".join(steps))

        add_log(task_id, "Supervisor", f"Decision: {response}")

        if "APPROVED" in response:
            return True
        return False
    
    def finalize(self, task_id: int, analysis: str):
        add_log(task_id, "Supervisor", f"Task complete. Final verdict: {analysis[:100]}")


class ExecutorAgent:
    def run(self, task_id: int, steps: list, user_input: str) -> str:
        add_log(task_id, "Executor", "Starting execution")

        results = []

        for i, step in enumerate(steps, 1):
            add_log(task_id, "Executor", f"Running step {i}: {step}")

            # 🧠 Tool-based routing
            if "search" in step.lower():
                step_result = f"(Simulated search result for: {step})"

            elif "calculate" in step.lower():
                step_result = "Calculated result: 42"

            else:
                system_prompt = """You are an executor. Complete the step concisely."""
                step_result = call_llm(
                    system_prompt,
                    f"Task: {user_input}\nStep: {step}"
                )

            results.append(f"Step {i}: {step_result}")
            add_log(task_id, "Executor", f"Completed step {i}")

        final = "\n\n".join(results)
        add_log(task_id, "Executor", "All steps completed")

        return final


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
    
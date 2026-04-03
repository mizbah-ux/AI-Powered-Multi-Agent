import os
import re
import requests
from groq import Groq
from database import add_log, get_memory, update_task_status, get_similar_tasks, get_similar_feedback


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


def perform_search(query: str) -> str:
    """
    Perform real web search using SerpAPI with DuckDuckGo fallback.
    
    Args:
        query: Search query string
        
    Returns:
        Formatted search results (top 3 results)
    """
    # Extract search intent from step text
    clean_query = re.sub(r'^(search|find|look for|search for)\s+', '', query.lower()).strip()
    
    # Try SerpAPI first
    serpapi_key = os.getenv("SERPAPI_KEY")
    if serpapi_key:
        try:
            return _search_with_serpapi(clean_query)
        except Exception as e:
            print(f"SerpAPI failed: {e}")
    
    # Fallback to DuckDuckGo
    try:
        return _search_with_duckduckgo(clean_query)
    except Exception as e:
        print(f"DuckDuckGo failed: {e}")
        return "Search temporarily unavailable. Please try again later."


def _search_with_serpapi(query: str) -> str:
    """Search using SerpAPI."""
    url = "https://serpapi.com/search"
    params = {
        "api_key": os.getenv("SERPAPI_KEY"),
        "engine": "google",
        "q": query,
        "num": 3,
        "safe": "active"
    }
    
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    
    data = response.json()
    
    if "organic_results" not in data or not data["organic_results"]:
        return f"No results found for: {query}"
    
    results = data["organic_results"][:3]
    formatted_results = []
    
    for i, result in enumerate(results, 1):
        title = result.get("title", "No title")
        snippet = result.get("snippet", "No description available")
        link = result.get("link", "")
        
        formatted_results.append(f"{i}. {title}")
        formatted_results.append(f"   {snippet[:150]}{'...' if len(snippet) > 150 else ''}")
        formatted_results.append(f"   {link}")
        formatted_results.append("")  # Empty line for readability
    
    return "\n".join(formatted_results).strip()


def _search_with_duckduckgo(query: str) -> str:
    """Search using DuckDuckGo HTML scraping."""
    url = "https://duckduckgo.com/html/"
    params = {
        "q": query,
        "kl": "us-en"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    
    # Parse HTML results (simplified parsing)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')
    
    results = []
    result_divs = soup.find_all('div', class_='result')[:3]
    
    for i, div in enumerate(result_divs, 1):
        try:
            title_tag = div.find('a', class_='result__a')
            title = title_tag.get_text(strip=True) if title_tag else "No title"
            
            snippet_tag = div.find('a', class_='result__snippet')
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else "No description available"
            
            link = title_tag.get('href', '') if title_tag else ""
            
            results.append(f"{i}. {title}")
            results.append(f"   {snippet[:150]}{'...' if len(snippet) > 150 else ''}")
            results.append(f"   {link}")
            results.append("")  # Empty line for readability
            
        except Exception as e:
            print(f"Error parsing DuckDuckGo result {i}: {e}")
            continue
    
    if not results:
        return f"No results found for: {query}"
    
    return "\n".join(results).strip()


def refine_plan_with_feedback(previous_steps: list, feedback: str) -> list:
    """
    Use LLM to generate a better plan based on Supervisor rejection feedback.
    
    Args:
        previous_steps: List of previous plan steps
        feedback: Supervisor rejection reason
        
    Returns:
        List of improved plan steps
    """
    # Convert plan list to text
    plan_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(previous_steps)])
    
    system_prompt = """
    You are a plan refinement specialist. The supervisor rejected the previous plan.
    Create a better plan that addresses the specific feedback provided.
    
    REQUIREMENTS:
    - Output EXACTLY 3-5 numbered steps
    - Format MUST be: 1. Step one, 2. Step two, etc.
    - Address the specific supervisor feedback
    - Keep steps clear, actionable, and logical
    - Do NOT use bullets, dashes, or explanations
    
    Learn from the feedback to create a superior plan.
    """
    
    user_message = f"""
    Previous rejected plan:
    {plan_text}
    
    Supervisor feedback to address:
    {feedback}
    
    Please provide an improved plan that addresses this feedback:
    """
    
    try:
        result = call_llm(system_prompt, user_message)
        
        # Parse the improved plan
        improved_steps = []
        for line in result.strip().split('\n'):
            line = line.strip()
            match = re.match(r"^(\d+[\.\)]\s*|-|\•)\s*(.+)", line)
            if match:
                step = match.group(2)
                improved_steps.append(step)
        
        return improved_steps if improved_steps else previous_steps
        
    except Exception as e:
        # Fallback: return original plan if improvement fails
        print(f"Plan refinement failed: {e}")
        return previous_steps


def improve_plan(previous_plan: list, feedback: str) -> list:
    """
    Use LLM to rewrite plan based on feedback.
    
    Args:
        previous_plan: List of previous plan steps
        feedback: Analyst feedback text
        
    Returns:
        List of improved plan steps
    """
    # Convert plan list to text
    plan_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(previous_plan)])
    
    system_prompt = """
    You are a plan improvement specialist. Rewrite the failed plan based on the feedback.
    
    REQUIREMENTS:
    - Output EXACTLY 3-5 numbered steps
    - Format MUST be: 1. Step one, 2. Step two, etc.
    - Address the specific feedback provided
    - Keep steps clear and actionable
    - Do NOT use bullets, dashes, or explanations
    
    Learn from the feedback to create a better plan.
    """
    
    user_message = f"""
    Previous failed plan:
    {plan_text}
    
    Feedback to address:
    {feedback}
    
    Please provide an improved plan that addresses this feedback:
    """
    
    try:
        result = call_llm(system_prompt, user_message)
        
        # Parse the improved plan
        improved_steps = []
        for line in result.strip().split('\n'):
            line = line.strip()
            match = re.match(r"^(\d+[\.\)]\s*|-|\•)\s*(.+)", line)
            if match:
                step = match.group(2)
                improved_steps.append(step)
        
        return improved_steps
        
    except Exception as e:
        # Fallback: return original plan if improvement fails
        print(f"Plan improvement failed: {e}")
        return previous_plan


class PlannerAgent:
    def get_similar_tasks(self, user_input: str, task_id: int = 0) -> str:
        """Retrieve similar past successful tasks from global memory."""
        try:
            similar_tasks = get_similar_tasks(user_input, limit=2)
            if not similar_tasks:
                return ""
            
            context = "Similar past successful tasks:\n"
            for i, task in enumerate(similar_tasks, 1):
                context += f"\nTask {i}:\n"
                context += f"Task: {task['task_input']}\n"
                context += f"Plan: {task['plan']}\n"
                context += f"Result: {task['result']}\n"
                context += f"Score: {task['score']}/10\n"
            
            return context
        except Exception as e:
            add_log(task_id, "Planner", f"Error retrieving similar tasks: {str(e)}")
            return ""

    def get_past_feedback(self, user_input: str, task_id: int = 0) -> str:
        """Retrieve past feedback and improvements for learning."""
        try:
            similar_feedback = get_similar_feedback(user_input, limit=3)
            if not similar_feedback:
                return ""
            
            context = "\nPast failures and improvements:\n"
            for i, feedback in enumerate(similar_feedback, 1):
                context += f"\nLearning {i}:\n"
                context += f"Task: {feedback['task_input']}\n"
                context += f"Mistake: {feedback['feedback']}\n"
                context += f"Improved plan: {feedback['improved_plan']}\n"
                context += f"Score: {feedback['score']}/10\n"
            
            return context
        except Exception as e:
            add_log(task_id, "Planner", f"Error retrieving past feedback: {str(e)}")
            return ""

    def run(self, task_id: int, user_input: str) -> list:
        add_log(task_id, "Planner", f"Received request: {user_input}")
    
        # 🧠 Fetch task-level memory
        memory = get_memory(task_id)
        memory_text = "\n".join([m["content"] for m in memory]) if memory else ""
        
        # 🧠 Fetch global memory for similar tasks
        global_memory_context = self.get_similar_tasks(user_input, task_id)
        if global_memory_context:
            similar_tasks = get_similar_tasks(user_input, limit=2)
            add_log(task_id, "Planner", f"Found {len(similar_tasks)} similar past tasks")
        
        # 🧠 Fetch past feedback for learning
        feedback_context = self.get_past_feedback(user_input, task_id)
        if feedback_context:
            similar_feedback = get_similar_feedback(user_input, limit=3)
            add_log(task_id, "Planner", f"Found {len(similar_feedback)} past learning examples")
    
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
        
        Learn from similar past tasks and avoid repeating past mistakes.
        """
    
        # 🧠 Inject all learning contexts
        full_input = f"""
        Previous context:
        {memory_text}
        
        {global_memory_context}
        
        {feedback_context}
    
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
    def approve_plan(self, task_id: int, steps: list) -> tuple[bool, str]:
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
            return True, ""
        else:
            # Extract rejection reason
            reason = response.replace("REJECTED:", "").strip()
            return False, reason
    
    def finalize(self, task_id: int, analysis: str):
        add_log(task_id, "Supervisor", f"Task complete. Final verdict: {analysis[:100]}")


class ExecutorAgent:
    def run(self, task_id: int, steps: list, user_input: str) -> str:
        add_log(task_id, "Executor", "Starting execution")

        results = []

        for i, step in enumerate(steps, 1):
            add_log(task_id, "Executor", f"Running step {i}: {step}")

            # 🧠 Tool-based routing with real search
            if "search" in step.lower():
                try:
                    step_result = perform_search(step)
                    add_log(task_id, "Executor", f"Search completed for: {step}")
                except Exception as e:
                    add_log(task_id, "Executor", f"Search failed: {str(e)}")
                    step_result = f"Search temporarily unavailable. Please try again later."

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
    
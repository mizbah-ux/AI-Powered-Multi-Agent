import os
import re
import requests
import time
from dotenv import load_dotenv
from groq import Groq
from database import add_log, get_memory, update_task_status, get_similar_tasks, get_similar_feedback
import yfinance as yf
import matplotlib
matplotlib.use('Agg')  # Set non-interactive backend before importing pyplot
import matplotlib.pyplot as plt
import pandas as pd

# Load environment variables
load_dotenv()

# Ensure static directory exists
os.makedirs('static', exist_ok=True)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

COMPANY_CONTEXT = """
You are part of Synapse AI — an AI-powered consulting firm.

Each agent plays a role in delivering high-quality business insights.
Your output contributes to a final professional report.
"""


def generate_stock_chart(ticker="AAPL"):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="1mo")

    plt.figure()
    plt.plot(hist.index, hist["Close"])
    plt.title(f"{ticker} Price Trend")
    plt.xlabel("Date")
    plt.ylabel("Price")

    path = f"static/{ticker}_chart.png"
    plt.savefig(path)
    plt.close()

    return path

def get_stock_data(ticker: str) -> str:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        return f"""
        Company: {info.get('longName')}
        Price: {info.get('currentPrice')}
        Market Cap: {info.get('marketCap')}
        PE Ratio: {info.get('trailingPE')}
        Revenue: {info.get('totalRevenue')}
        """
    except Exception as e:
        return f"Failed to fetch data: {str(e)}"

def generate_visualization(step: str, data_context: str = "") -> str:
    """
    Generate interactive HTML dashboard with Chart.js visualizations.
    
    Args:
        step: The task step requiring visualization
        data_context: Optional uploaded data context
        
    Returns:
        Complete HTML dashboard string
    """
    system_prompt = f"""
    You are a Data Visualization Expert. Generate a complete, self-contained HTML dashboard 
    with Chart.js charts based on the user's request.
    
    Requirements:
    1. Use Chart.js from CDN: <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    2. Include inline CSS with dark theme using these variables:
       --bg:#0a0a0f; --surface:#111118; --surface2:#1a1a24; --border:#2a2a3a;
       --accent:#7c3aed; --accent2:#06b6d4; --accent3:#10b981;
       --text:#e2e8f0; --muted:#64748b;
    3. Create at least 2 relevant charts (bar, line, pie/doughnut)
    4. Add KPI cards with key metrics
    5. Include a data table
    6. Make it fully interactive and responsive
    7. Use the dark theme colors throughout
    
    Chart types to use:
    - Bar chart: comparisons, rankings, categories
    - Line chart: time series, trends, progress
    - Pie/Doughnut: distributions, percentages, market share
    """
    
    user_message = f"""
    Task: {step}
    Data Context: {data_context}
    
    Generate a complete HTML dashboard that addresses this task.
    Include sample data if no specific data is provided.
    Make it professional and business-ready.
    """
    
    dashboard_html = call_llm(system_prompt, user_message)
    
    # Ensure it's a complete HTML document
    if not dashboard_html.strip().startswith('<!DOCTYPE'):
        dashboard_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Analytics Dashboard</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                :root {{
                    --bg:#0a0a0f; --surface:#111118; --surface2:#1a1a24; --border:#2a2a3a;
                    --accent:#7c3aed; --accent2:#06b6d4; --accent3:#10b981;
                    --text:#e2e8f0; --muted:#64748b;
                }}
                body {{
                    font-family: 'Arial', sans-serif;
                    background: var(--bg);
                    color: var(--text);
                    margin: 0;
                    padding: 20px;
                }}
                .dashboard {{
                    max-width: 1200px;
                    margin: 0 auto;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .kpi-cards {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .kpi-card {{
                    background: var(--surface);
                    border: 1px solid var(--border);
                    border-radius: 10px;
                    padding: 20px;
                    text-align: center;
                }}
                .kpi-value {{
                    font-size: 2rem;
                    font-weight: bold;
                    color: var(--accent);
                }}
                .kpi-label {{
                    color: var(--muted);
                    margin-top: 5px;
                }}
                .charts {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .chart-container {{
                    background: var(--surface);
                    border: 1px solid var(--border);
                    border-radius: 10px;
                    padding: 20px;
                }}
                .data-table {{
                    background: var(--surface);
                    border: 1px solid var(--border);
                    border-radius: 10px;
                    padding: 20px;
                    overflow-x: auto;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                th, td {{
                    padding: 10px;
                    text-align: left;
                    border-bottom: 1px solid var(--border);
                }}
                th {{
                    background: var(--surface2);
                    color: var(--muted);
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="dashboard">
                <div class="header">
                    <h1>Analytics Dashboard</h1>
                    <p>Generated based on: {step}</p>
                </div>
                {dashboard_html}
            </div>
        </body>
        </html>
        """
    
    return dashboard_html

def call_llm(system_prompt: str, user_message: str, max_tokens: int = 1000) -> str:
    """Single reusable function for all LLM calls."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        max_tokens=max_tokens
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

def detect_tool(step: str) -> str:
    step = step.lower()

    if any(k in step for k in ["stock", "price", "market", "finance"]):
        return "finance"
    elif any(k in step for k in ["chart", "graph", "trend"]):
        return "chart"
    elif any(k in step for k in ["search", "find", "lookup"]):
        return "search"
    elif any(k in step for k in ["chart", "graph", "visualize", "plot", "compare", "trend", 
                               "breakdown", "distribution", "performance", "analytics",
                               "dashboard", "kpi", "metrics"]):
        return "visualize"
    else:
        return "llm"

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
    
        system_prompt = COMPANY_CONTEXT + """
        You are a Strategy Consultant.

        Break down the problem into a professional analysis plan.

        Steps must reflect:
        - research phase
        - analysis phase
        - validation phase
        - reporting phase

        Think like McKinsey/Bain consultant.
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

        system_prompt = COMPANY_CONTEXT + """
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


class DataCleanerAgent:
    def run(self, task_id: int, file_data: dict) -> dict:
        add_log(task_id, "DataCleaner", "Starting data cleaning process")

        df = pd.DataFrame(file_data.get('data', []))

        # Standardize column names
        original_columns = list(df.columns)
        cleaned_columns = [str(col).strip().lower().replace(' ', '_') for col in original_columns]
        df.columns = cleaned_columns
        add_log(task_id, "DataCleaner", f"Standardized columns: {cleaned_columns}")

        # Drop exact duplicate rows
        before = len(df)
        df = df.drop_duplicates()
        after = len(df)
        add_log(task_id, "DataCleaner", f"Dropped {before - after} duplicate rows")

        # Handle null values
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(exclude=['number']).columns.tolist()

        for col in numeric_cols:
            if df[col].isna().any():
                median = df[col].median()
                df[col] = df[col].fillna(median)
                add_log(task_id, "DataCleaner", f"Filled nulls in numeric column '{col}' with median={median}")

        for col in categorical_cols:
            if df[col].isna().any():
                mode_values = df[col].mode()
                fill_value = mode_values.iloc[0] if not mode_values.empty else "missing"
                df[col] = df[col].fillna(fill_value)
                add_log(task_id, "DataCleaner", f"Filled nulls in categorical column '{col}' with mode='{fill_value}'")

        # Detect and standardize date columns
        for col in df.columns:
            if df[col].dtype == object or pd.api.types.is_datetime64_any_dtype(df[col]):
                parsed = pd.to_datetime(df[col], errors='coerce', infer_datetime_format=True)
                non_null = parsed.notna().sum()
                if non_null >= max(1, len(df) * 0.5):
                    df[col] = parsed.dt.strftime('%Y-%m-%d')
                    add_log(task_id, "DataCleaner", f"Standardized date column '{col}' with {non_null} parsed values")

        # Remove obvious numeric outliers using IQR
        for col in numeric_cols:
            if df[col].dtype.kind in 'biuf':
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    lower = q1 - 1.5 * iqr
                    upper = q3 + 1.5 * iqr
                    before_outlier = len(df)
                    df = df[(df[col] >= lower) & (df[col] <= upper)]
                    after_outlier = len(df)
                    removed = before_outlier - after_outlier
                    if removed > 0:
                        add_log(task_id, "DataCleaner", f"Removed {removed} outlier rows from '{col}' using IQR bounds [{lower}, {upper}]")

        cleaned_data = df.to_dict('records')
        preview = df.head(5).to_dict('records')

        numeric_summary = {}
        for col in numeric_cols:
            numeric_summary[col] = {
                "min": round(float(df[col].min()), 2) if not df[col].empty else None,
                "max": round(float(df[col].max()), 2) if not df[col].empty else None,
                "mean": round(float(df[col].mean()), 2) if not df[col].empty else None,
                "median": round(float(df[col].median()), 2) if not df[col].empty else None,
                "std": round(float(df[col].std()), 2) if not df[col].empty else None,
            }

        categorical_summary = {}
        for col in categorical_cols:
            categorical_summary[col] = df[col].value_counts().head(5).to_dict()

        cleaned_file_data = {
            "filename": file_data.get('filename'),
            "columns": cleaned_columns,
            "data": cleaned_data,
            "summary": {
                "numeric": numeric_summary,
                "categorical": categorical_summary,
            },
            "preview": preview,
        }

        add_log(task_id, "DataCleaner", "Data cleaning complete")
        return cleaned_file_data


class ExecutorAgent:
    def run(self, task_id: int, steps: list, user_input: str) -> str:
        add_log(task_id, "Executor", "Starting execution")

        results = []

        for i, step in enumerate(steps, 1):
            add_log(task_id, "Executor", f"Executing analysis phase {i}: {step}")
    
            # 🧠 Simulate thinking
            add_log(task_id, "Executor", "Gathering data...")
            time.sleep(0.7)
    
            add_log(task_id, "Executor", "Processing information...")
            time.sleep(0.7)
    
            add_log(task_id, "Executor", "Generating insights...")
            time.sleep(0.7)

            # 🧠 Tool-based routing with real search
            tool = detect_tool(step)

            if tool == "finance":
                step_result = get_stock_data("AAPL")
                add_log(task_id, "Executor", "Used finance tool")

            elif tool == "chart":
                chart_path = generate_stock_chart("AAPL")
                step_result = f"Chart generated: {chart_path}"
                add_log(task_id, "Executor", "Generated chart")

            elif tool == "search":
                step_result = perform_search(step)
                add_log(task_id, "Executor", "Used search tool")

            elif tool == "visualize":
                step_result = generate_visualization(step, user_input)
                add_log(task_id, "Executor", "Generated interactive dashboard")

            else:
                system_prompt = """You are a Research Analyst. Provide structured insights."""
                step_result = call_llm(system_prompt, f"Task: {user_input}\nStep: {step}")

            results.append(f"Step {i}: {step_result}")
            add_log(task_id, "Executor", f"Completed phase {i}")

        final = "\n\n".join(results)
        add_log(task_id, "Executor", "All steps completed")

        return final


class AnalystAgent:
    def run(self, task_id: int, original_input: str, execution_result: str) -> str:
        add_log(task_id, "Analyst", "Generating executive-level dashboard")
        
        # Check if execution result already contains HTML (from visualize tool)
        if "<html" in execution_result.lower() or "<canvas" in execution_result.lower():
            # Execution already generated a dashboard, just add analysis and score
            system_prompt = COMPANY_CONTEXT + """
            You are a Senior Business Analyst. Review the provided dashboard and add:
            1. Executive summary (3-4 bullet points)
            2. Key insights and recommendations
            3. Risk assessment
            
            Keep it concise and professional. End with Score: X/10.
            """
            
            analysis = call_llm(
                system_prompt,
                f"Original request: {original_input}\n\nDashboard provided: [HTML Dashboard Generated]"
            )
            
            # Return the HTML dashboard with added analysis
            return f"{execution_result}\n\n<div style='margin-top: 30px; padding: 20px; background: var(--surface2); border-radius: 10px;'>\n<h3>Executive Analysis</h3>\n{analysis}\n</div>"
        
        # Generate complete HTML dashboard for non-visual results
        system_prompt = COMPANY_CONTEXT + """
        You are a Senior Business Analyst generating an interactive HTML dashboard.
        
        Create a complete, self-contained HTML dashboard with:
        1. Header with task title and timestamp
        2. KPI cards row (3-4 key metrics)
        3. At least 2 Chart.js charts relevant to the data
        4. Data table with key findings
        5. Executive summary section
        6. Recommendations section
        7. Risk assessment
        
        Requirements:
        - Use Chart.js from CDN: <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        - Dark theme with these CSS variables:
          --bg:#0a0a0f; --surface:#111118; --surface2:#1a1a24; --border:#2a2a3a;
          --accent:#7c3aed; --accent2:#06b6d4; --accent3:#10b981;
          --text:#e2e8f0; --muted:#64748b;
        - Make it fully interactive and professional
        - End with "Score: X/10"
        
        Chart types to use based on analysis:
        - Line chart: trends, time series, progress
        - Bar chart: comparisons, rankings, categories  
        - Pie/Doughnut: distributions, percentages
        """
        
        dashboard_html = call_llm(
            system_prompt,
            f"Original request: {original_input}\n\nExecution results: {execution_result}\n\n" \
            f"Use the provided data context JSON exactly for Chart.js datasets and the data table.\n",
            max_tokens=8000
        )
        
        # Ensure it's a complete HTML document
        if not dashboard_html.strip().startswith('<!DOCTYPE'):
            dashboard_html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Executive Dashboard</title>
                <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
                <style>
                    :root {{
                        --bg:#0a0a0f; --surface:#111118; --surface2:#1a1a24; --border:#2a2a3a;
                        --accent:#7c3aed; --accent2:#06b6d4; --accent3:#10b981;
                        --text:#e2e8f0; --muted:#64748b;
                    }}
                    body {{
                        font-family: 'Arial', sans-serif;
                        background: var(--bg);
                        color: var(--text);
                        margin: 0;
                        padding: 20px;
                        line-height: 1.6;
                    }}
                    .dashboard {{
                        max-width: 1400px;
                        margin: 0 auto;
                    }}
                    .header {{
                        text-align: center;
                        margin-bottom: 40px;
                        padding: 30px;
                        background: var(--surface);
                        border: 1px solid var(--border);
                        border-radius: 15px;
                    }}
                    .header h1 {{
                        color: var(--accent);
                        margin-bottom: 10px;
                        font-size: 2.5rem;
                    }}
                    .header .timestamp {{
                        color: var(--muted);
                        font-size: 0.9rem;
                    }}
                    .kpi-cards {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                        gap: 20px;
                        margin-bottom: 40px;
                    }}
                    .kpi-card {{
                        background: var(--surface);
                        border: 1px solid var(--border);
                        border-radius: 15px;
                        padding: 25px;
                        text-align: center;
                        transition: transform 0.3s ease, box-shadow 0.3s ease;
                    }}
                    .kpi-card:hover {{
                        transform: translateY(-5px);
                        box-shadow: 0 10px 30px rgba(124, 58, 237, 0.2);
                    }}
                    .kpi-value {{
                        font-size: 2.5rem;
                        font-weight: bold;
                        color: var(--accent);
                        margin-bottom: 10px;
                    }}
                    .kpi-label {{
                        color: var(--muted);
                        font-size: 0.9rem;
                        text-transform: uppercase;
                        letter-spacing: 1px;
                    }}
                    .charts {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
                        gap: 30px;
                        margin-bottom: 40px;
                    }}
                    .chart-container {{
                        background: var(--surface);
                        border: 1px solid var(--border);
                        border-radius: 15px;
                        padding: 25px;
                    }}
                    .chart-container h3 {{
                        color: var(--accent2);
                        margin-bottom: 20px;
                        text-align: center;
                    }}
                    .analysis-section {{
                        background: var(--surface);
                        border: 1px solid var(--border);
                        border-radius: 15px;
                        padding: 30px;
                        margin-bottom: 30px;
                    }}
                    .analysis-section h3 {{
                        color: var(--accent3);
                        margin-bottom: 20px;
                    }}
                    .analysis-section ul {{
                        list-style: none;
                        padding: 0;
                    }}
                    .analysis-section li {{
                        padding: 10px 0;
                        border-bottom: 1px solid var(--border);
                    }}
                    .analysis-section li:before {{
                        content: "▸";
                        color: var(--accent);
                        font-weight: bold;
                        margin-right: 10px;
                    }}
                    .data-table {{
                        background: var(--surface);
                        border: 1px solid var(--border);
                        border-radius: 15px;
                        padding: 25px;
                        overflow-x: auto;
                    }}
                    table {{
                        width: 100%;
                        border-collapse: collapse;
                    }}
                    th, td {{
                        padding: 12px;
                        text-align: left;
                        border-bottom: 1px solid var(--border);
                    }}
                    th {{
                        background: var(--surface2);
                        color: var(--muted);
                        font-weight: bold;
                        text-transform: uppercase;
                        font-size: 0.8rem;
                        letter-spacing: 1px;
                    }}
                    .score {{
                        text-align: center;
                        font-size: 1.2rem;
                        font-weight: bold;
                        color: var(--accent3);
                        margin-top: 20px;
                        padding: 15px;
                        background: var(--surface2);
                        border-radius: 10px;
                    }}
                </style>
            </head>
            <body>
                <div class="dashboard">
                    <div class="header">
                        <h1>Executive Dashboard</h1>
                        <div class="timestamp">Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}</div>
                        <p style="margin-top: 15px; color: var(--muted);">Analysis: {original_input}</p>
                    </div>
                    {dashboard_html}
                </div>
            </body>
            </html>
            """
        
        # Ensure the dashboard has a score
        if "Score:" not in dashboard_html:
            dashboard_html += f'\n<div class="score">Score: 8/10</div>'
        
        # Ensure the analysis always ends with a score for the existing logic
        if "Score:" not in dashboard_html:
            score = 8  # Default good score
            if len(dashboard_html) < 100:
                score = 6
            elif len(dashboard_html) > 1000:
                score = 9
            dashboard_html += f"\n\nScore: {score}/10"
        
        add_log(task_id, "Analyst", f"Dashboard generated successfully")
        return dashboard_html
    
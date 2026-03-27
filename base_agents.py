import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process

load_dotenv()

# CrewAI looks for this specific environment variable name for Groq
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")
MODEL = "groq/llama-3.3-70b-versatile"  

# 1. Define Agents (Stay the same)
planner = Agent(
    role="Strategic Planner",
    goal="Decompose the user's request into actionable tasks for {topic}.",
    backstory="Expert in workflow optimization and task breakdown.",
    llm=MODEL,
    allow_delegation=False,
    verbose=True
)

executor = Agent(
    role="Operations Specialist",
    goal="Produce the actual content or data requested for {topic}.",
    backstory="Efficient worker who follows the planner's roadmap.",
    llm=MODEL,
    allow_delegation=False,
    verbose=True
)

analyst = Agent(
    role="Quality Auditor",
    goal="Verify the output for accuracy regarding {topic}.",
    backstory="Perfectionist who ensures the work meets the original goal.",
    llm=MODEL,
    allow_delegation=False,
    verbose=True
)

supervisor = Agent(
    role="Project Manager",
    goal="Coordinate the team and provide the final polished output for {topic}.",
    backstory="The lead who ensures the final result is ready for the client.",
    llm=MODEL,
    allow_delegation=True,
    verbose=True
)

# 2. Define the Task with curly brace placeholders {topic}
test_task = Task(
    description=(
        "Analyze the requirements for starting a {topic} business. "
        "Provide a high-level 3-step startup plan tailored specifically to {topic}."
    ),
    expected_output="A structured 3-step plan with brief descriptions and technical milestones.",
    agent=supervisor 
)

# 3. Define the Crew
crew = Crew(
    agents=[planner, executor, analyst, supervisor],
    tasks=[test_task],
    process=Process.sequential,
    verbose=True
)

if __name__ == "__main__":
    print("### STARTING MULTI-AGENT SYSTEM ###")
    
    # NEW: Define your inputs here
    # You can change this to "Smart Waste Management" or "Hospital Logistics"
    inputs = {
        'topic': 'Freelance Web Development' 
    }
    
    try:
        # Pass the inputs dictionary into the kickoff method
        result = crew.kickoff(inputs=inputs)
        
        print("\n\n########################")
        print(f"## FINAL REPORT FOR: {inputs['topic']} ##")
        print("########################\n")
        print(result)
    except Exception as e:
        print(f"AN ERROR OCCURRED: {e}")
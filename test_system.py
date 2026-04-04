#!/usr/bin/env python3
"""
Test script to verify the multi-agent system is working
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_imports():
    """Test all imports"""
    try:
        print("Testing imports...")
        from main import app
        from agents import PlannerAgent, SupervisorAgent, ExecutorAgent, AnalystAgent
        from database import init_db, get_all_tasks
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_database():
    """Test database connection"""
    try:
        print("Testing database...")
        from database import init_db, get_all_tasks
        init_db()
        tasks = get_all_tasks()
        print(f"✅ Database working. Found {len(tasks)} tasks")
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_groq_client():
    """Test Groq API client"""
    try:
        print("Testing Groq client...")
        from groq import Groq
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        print(f"✅ Groq client created. API key length: {len(os.getenv('GROQ_API_KEY', ''))}")
        return True
    except Exception as e:
        print(f"❌ Groq client error: {e}")
        return False

def test_fastapi():
    """Test FastAPI app"""
    try:
        print("Testing FastAPI app...")
        from main import app
        print("✅ FastAPI app loaded successfully")
        return True
    except Exception as e:
        print(f"❌ FastAPI error: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Testing Multi-Agent System Setup")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_database,
        test_groq_client,
        test_fastapi
    ]
    
    results = []
    for test in tests:
        results.append(test())
        print()
    
    passed = sum(results)
    total = len(results)
    
    print("=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! System is ready to run.")
        return True
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

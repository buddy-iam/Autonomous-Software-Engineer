import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_community.tools.tavily_search import TavilySearchResults

load_dotenv()

# 1. Heavy LLM for Project Manager & Coder
heavy_llm = ChatGroq(
    model="qwen/qwen3.8-27b", 
    temperature=0.1, 
    max_tokens=8000
)

# 2. Light LLM for Intent Classifier, Q&A, & Routing
light_llm = ChatGroq(
    model="qwen/qwen3.8-27b", 
    temperature=0.1, 
    max_tokens=800
)

tavily_tool = TavilySearchResults(max_results=3)
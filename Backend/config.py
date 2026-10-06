import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_tavily import TavilySearchResults

load_dotenv()

# Heavy LLM for coding
heavy_llm = ChatGroq(
    model="openai/gpt-oss-120b", 
    temperature=0.1, 
    max_tokens=3000,
    max_retries=3
)

# Light LLM for planning and chatting
light_llm = ChatGroq(
    model="openai/gpt-oss-20b", 
    temperature=0.7, 
    max_tokens=800,
    max_retries=3
)

tavily_tool = TavilySearchResults(max_results=3)
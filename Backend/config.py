import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_community.tools.tavily_search import TavilySearchResults

load_dotenv()

# Heavy LLM: Lowered tokens to 3000 to prevent TPM cap, added max_retries
heavy_llm = ChatGroq(
    model="openai/gpt-oss-120b", 
    temperature=0.1, 
    max_tokens=3000,
    max_retries=3
)

# Light LLM: Switched to 8B model to utilize 30,000 TPM free tier quota
light_llm = ChatGroq(
    model="openai/gpt-oss-20b", 
    temperature=0.1, 
    max_tokens=800,
    max_retries=3
)

tavily_tool = TavilySearchResults(max_results=3)
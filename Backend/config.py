import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper

load_dotenv()

# Heavy LLM for planning, full-file coding, and diff edits
heavy_llm = ChatGroq(
    model="openai/gpt-oss-120b", 
    temperature=0.1, 
    max_tokens=3000,
    max_retries=3
)

# Light LLM for general knowledge, search synthesis, and QA
light_llm = ChatGroq(
    model="openai/gpt-oss-20b", 
    temperature=0.7, 
    max_tokens=1000,
    max_retries=3
)

tavily_tool = TavilySearchResults(max_results=3)
wikipedia_tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper(top_k_results=2, doc_content_chars_max=1500))
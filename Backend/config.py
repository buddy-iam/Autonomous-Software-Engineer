import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

# Initialize the shared LLM instance
llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.1)
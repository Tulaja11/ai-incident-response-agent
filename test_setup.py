import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()
print("Key loaded:", bool(os.getenv("GOOGLE_API_KEY")))

llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0)
print(llm.invoke("Reply with exactly: OK").content)
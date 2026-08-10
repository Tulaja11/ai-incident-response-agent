import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("Models supporting embedContent:\n")
for m in client.models.list():
    actions = getattr(m, "supported_actions", None) or []
    if "embedContent" in actions:
        print(" ", m.name)
from dotenv import load_dotenv
import os
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL"),
)

ACTIVE_MODEL = os.getenv("LLM_MODEL", "openrouter/free")

response = client.chat.completions.create(
    model=ACTIVE_MODEL,
    messages=[
        {"role": "user", "content": "Say hello."}
    ],
)

print(response.choices[0].message.content)
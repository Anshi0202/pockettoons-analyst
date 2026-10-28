from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()          # 1. reads .env and puts OPENAI_API_KEY into the environment
client = OpenAI()      # 2. the client finds OPENAI_API_KEY there automatically

resp = client.responses.create(   # 3. sends one request to OpenAI
    model="gpt-6-luna",
    input="Say 'connection works'",
)
print(resp.output_text)           # 4. prints the model's reply
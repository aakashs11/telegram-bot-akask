import openai
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

class OpenAI:
    def __init__(self):
        pass
    # Add custom helper methods if needed

client = OpenAI()

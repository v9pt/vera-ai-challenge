import os
import json
from urllib import request as urlrequest
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Pre-initialize Groq client as fallback if the key exists
groq_api_key = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=groq_api_key) if groq_api_key else None


def generate_message(prompt: str) -> str:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    
    if gemini_api_key:
        try:
            model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_api_key}"
            
            body = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.0,
                    "maxOutputTokens": 1000
                }
            }).encode("utf-8")
            
            req = urlrequest.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
            )
            
            resp = urlrequest.urlopen(req, timeout=15)
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            print("Gemini API error, falling back to Groq:", e)

    if groq_client:
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.0,  # Ensure determinism as required by challenge brief
                max_tokens=180
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print("Groq API error:", e)
            raise e

    raise ValueError("Neither GEMINI_API_KEY nor GROQ_API_KEY is configured in .env")
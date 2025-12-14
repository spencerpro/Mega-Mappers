import requests
import json
from typing import Dict, Any, List
from .base import AIProvider

class OpenAICompatibleProvider(AIProvider):
    def __init__(self):
        self.api_key = None
        self.base_url = None
        self.headers = {}

    def configure(self, api_key: str, base_url: str = None):
        self.api_key = api_key
        # Default to localhost (Ollama) if no URL provided
        self.base_url = base_url.rstrip('/') if base_url else "http://localhost:11434/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def list_models(self) -> List[str]:
        if not self.base_url: return []
        try:
            # Standard OpenAI endpoint for models
            url = f"{self.base_url}/models"
            response = requests.get(url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [m['id'] for m in data.get('data', [])]
            return [f"Error: {response.status_code}"]
        except Exception as e:
            return [f"Connection Failed: {str(e)}"]

    def generate_text(self, model: str, prompt: str, context: str = "") -> str:
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": context},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7
            }
            url = f"{self.base_url}/chat/completions"
            response = requests.post(url, headers=self.headers, json=payload, timeout=3000)
            
            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content']
            else:
                return f"AI Error ({response.status_code}): {response.text}"
        except Exception as e:
            return f"Request Error: {str(e)}"

    def generate_json(self, model: str, prompt: str, schema_hint: str = "") -> Dict[str, Any]:
        system_prompt = f"You are a data API. Output ONLY valid JSON matching this schema: {schema_hint}"
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"} # Supported by OpenAI/Groq/Ollama(latest)
            }
            url = f"{self.base_url}/chat/completions"
            response = requests.post(url, headers=self.headers, json=payload, timeout=3000)
            
            if response.status_code == 200:
                data = response.json()
                content = data['choices'][0]['message']['content']
                # Strip markdown if model misbehaves
                content = content.replace("```json", "").replace("```", "").strip()
                return json.loads(content)
            else:
                print(f"AI Error ({response.status_code}): {response.text}")
                return {}
        except Exception as e:
            print(f"JSON Request Error: {str(e)}")
            return {}

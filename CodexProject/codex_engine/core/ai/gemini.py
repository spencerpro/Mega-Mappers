import os
import json
import google.generativeai as genai
from typing import Dict, Any, List
from .base import AIProvider

class GeminiProvider(AIProvider):
    def __init__(self):
        self.api_key = None
        self.model = None

    def configure(self, api_key: str, base_url: str = None):
        self.api_key = api_key
        if self.api_key and self.api_key != "missing":
            genai.configure(api_key=self.api_key)

    def list_models(self) -> List[str]:
        if not self.api_key: return ["Error: Key Missing"]
        try:
            # Filter for models that support content generation
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            # Clean up names (remove 'models/')
            return [m.replace("models/", "") for m in models]
        except Exception as e:
            return [f"Error: {str(e)}"]

    def _get_model(self, model_name):
        return genai.GenerativeModel(model_name or "gemini-1.5-flash")

    def generate_text(self, model: str, prompt: str, context: str = "") -> str:
        if not self.api_key: return "AI Unavailable: Key missing."
        
        full_prompt = f"Context: {context}\n\nTask: {prompt}"
        try:
            response = self._get_model(model).generate_content(full_prompt)
            return response.text
        except Exception as e:
            return f"AI Error: {str(e)}"

    def generate_json(self, model: str, prompt: str, schema_hint: str = "") -> Dict[str, Any]:
        if not self.api_key: return {}

        sys_instruction = "You are a data API. Output ONLY valid JSON. No markdown formatting."
        full_prompt = f"{sys_instruction}\nSchema expected: {schema_hint}\nRequest: {prompt}"
        
        try:
            response = self._get_model(model).generate_content(full_prompt)
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            print(f"JSON Generation failed: {e}")
            return {}

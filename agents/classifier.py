import os
import json
import logging
import re
import requests
import urllib3
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


class ClassificationAgent:
    def __init__(self):
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.token = os.getenv("GROQ_API_KEY")
        if not self.token:
            raise ValueError("❌ GROQ_API_KEY missing from .env!")
        self.model = "llama-3.3-70b-versatile"

        session = requests.Session()
        retries = Retry(total=3, backoff_factor=1,
                        status_forcelist=[500, 502, 503, 504, 429],
                        allowed_methods=["POST"])
        session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session = session

    def process(self, raw_doc: dict) -> dict:
        """
        Sends the raw document content to Groq and returns structured RFQ data.
        """
        logging.info(f"🧠 Classifier: Analyzing '{raw_doc['filename']}'...")
        prompt = self._build_prompt(raw_doc["raw_content"])
        result = self._call_llm(prompt)

        if result:
            result["sender_email"] = raw_doc.get("sender_email")
            result["sender_company"] = raw_doc.get("sender_company", "Valued Customer")
            return result

        # Fallback if LLM fails
        return {
            "classification": "WARM",
            "confidence_score": 50,
            "tat_deadline": "24 Hours",
            "customer_name": raw_doc.get("sender_company", "Valued Customer"),
            "summary": "RFQ received — manual review needed",
            "extracted_items": [],
            "missing_info": ["LLM classification failed"],
            "sender_email": raw_doc.get("sender_email"),
            "sender_company": raw_doc.get("sender_company", "Valued Customer")
        }

    # ── Internal ───────────────────────────────────────────────

    def _build_prompt(self, content: str) -> str:
        return f"""
You are a Gold & Jewellery RFQ Classification AI for a jewellery seller.
Read the buyer's Request for Quotation below and extract structured data.

--- RFQ DOCUMENT ---
{content[:8000]}
--- END ---

### INSTRUCTIONS:
1. Classify urgency as HOT (urgent/high value), WARM (standard), or COLD.
2. Extract the customer/company name.
3. Extract ALL items requested with quantities.
   - For gold bars/coins: identify weight (e.g., "1KG bar", "100g bar", "10g coin")
   - For jewellery: identify type and approximate weight if mentioned
4. Assign TAT based on urgency.

### OUTPUT (strict JSON only, no extra text):
{{
    "classification": "HOT/WARM/COLD",
    "confidence_score": 90,
    "tat_deadline": "2 Hours / 24 Hours / 48 Hours",
    "customer_name": "Company or Person Name",
    "summary": "Brief one-line summary of the request",
    "extracted_items": [
        {{"item": "Gold Bar 1KG", "qty": "5", "purity": "24K", "notes": "any special requirements"}}
    ],
    "missing_info": ["list any missing specs"]
}}
"""

    def _call_llm(self, prompt: str):
        try:
            resp = self.session.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                json={"model": self.model, "max_tokens": 1500, "temperature": 0.1,
                      "messages": [{"role": "user", "content": prompt}]},
                verify=False, timeout=30
            )
            raw = resp.json()["choices"][0]["message"]["content"]
            return self._parse_json(raw)
        except Exception as e:
            logging.error(f"❌ LLM call failed: {e}")
            return None

    def _parse_json(self, raw: str):
        try:
            clean = raw.replace("```json", "").replace("```", "").strip()
            start, end = clean.find("{"), clean.rfind("}") + 1
            return json.loads(clean[start:end])
        except Exception:
            try:
                fixed = re.sub(r"'([^']+)':", r'"\1":', clean)
                fixed = re.sub(r": '([^']*)'", r': "\1"', fixed)
                return json.loads(fixed)
            except Exception:
                return None

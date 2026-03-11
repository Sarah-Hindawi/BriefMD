import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

if not os.getenv('GEMINI_API_KEY'):
    print("Warning: GEMINI_API_KEY not found in environment variables.")

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

def run(discharge_summary: str, flags: list[dict]) -> str:
    flag_text = "\n".join(
        f"- {f['test']}: {f['value']} {f['unit']} [{f['status']}]"
        for f in flags
    ) or "None detected."

    prompt = f"""You are a clinical handoff AI.

DISCHARGE SUMMARY:
{discharge_summary}

SENTINEL LAB FLAGS (anomalies detected):
{flag_text}

Generate a structured clinical briefing with these sections:
1. CLINICAL SUMMARY (10 sentences max)
2. KEY INTERVENTIONS
3. MEDICATION CHANGES
4. FLAGGED LAB ANOMALIES (reference the discharge summary and the sentinel flags above)
5. PENDING ITEMS & FOLLOW-UP URGENCY

Be concise."""

    response = model.generate_content(prompt)
    return response.text
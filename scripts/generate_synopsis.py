import os, time
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

if not os.getenv('LLM_API_KEY'):
    print("Warning: LLM_API_KEY not found in environment variables.")

client = Groq(api_key=os.getenv("LLM_API_KEY"))

def run(discharge_summary: str, similar_cases: list[dict] = None) -> str:

    if similar_cases:
        rag_context = "\n".join(
            f"- {c['admission_diagnosis']} | {c['gender']}, {c['age']}yo"
            for c in similar_cases
        )
    else:
        rag_context = "None available."

    prompt = f"""You are Brief MD, a clinical handoff AI that generates \
    structured briefings for primary care physicians receiving a patient \
    after an ER visit.

    DISCHARGE SUMMARY:
    {discharge_summary}

    SIMILAR PAST CASES (from clinical knowledge base):
    {rag_context}

    Generate a structured clinical briefing with exactly these sections:

    1. CLINICAL SUMMARY
    What happened, why the patient came in, current status. 3-4 sentences max.

    2. KEY INTERVENTIONS
    Procedures, treatments, and decisions made during the ER visit.

    3. MEDICATION CHANGES
    What was started, stopped, or adjusted. Flag any high-risk drugs \
    (anticoagulants, opioids, steroids, digoxin).

    4. PENDING ITEMS
    Anything unresolved: pending results, incomplete workups, \
    unconfirmed diagnoses.

    5. FOLLOW-UP URGENCY
    Who the patient needs to see, for what, and how soon. \
    Be specific — days, not "soon".

    Be clinical and concise. Write for a physician who has 2 minutes \
    before walking into the room."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content
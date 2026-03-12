EXTRACT_SYSTEM = "You are a clinical data extraction assistant. Return ONLY valid JSON. No explanation. No markdown."

SUMMARIZE_SYSTEM = (
    "You are a clinical summarizer. You write concise summaries "
    "for primary care physicians receiving a patient after hospital discharge. "
    "Write exactly 5 bullet points. Each bullet is one sentence. "
    "Focus on: what happened, what changed, what's dangerous, what needs follow-up."
)

SUMMARIZE_PROMPT = """Write a 5-bullet discharge summary for the receiving PCP.

Patient data:
- Chief complaint: {chief_complaint}
- Diagnoses: {diagnoses}
- Discharge medications: {medications}
- Allergies: {allergies}
- Follow-up plan: {follow_up}
- Missing sections in note: {missing}

Rules:
- Exactly 5 bullets
- Each bullet is ONE sentence
- Bullet 1: Who is this patient and why were they admitted
- Bullet 2: What was the main treatment/intervention
- Bullet 3: What changed (new meds, new diagnoses, resolved problems)
- Bullet 4: What's the biggest risk right now
- Bullet 5: What the PCP needs to do first
- No jargon the PCP wouldn't know
- If follow-up plan is vague or missing, say so explicitly"""

EXTRACT_PROMPT = """Extract data from this discharge summary into JSON.
Return ONLY valid JSON matching this schema exactly.

JSON schema:
{{
  "chief_complaint": "str",
  "admission_diagnosis": "str",
  "discharge_diagnosis": "str",
  "past_medical_history": ["str"],
  "family_history": "str",
  "social_history": "str",
  "diagnoses_mentioned": ["str"],
  "allergies": ["str"],
  "medications_discharge": [
    {{"name": "str", "dose": "str", "route": "str", "frequency": "str",
      "is_new": false, "is_changed": false, "is_stopped": false, "change_reason": ""}}
  ],
  "medications_stopped": [
    {{"name": "str", "dose": "str", "change_reason": "str"}}
  ],
  "lab_results_discussed": ["str"],
  "pending_tests": [
    {{"test_name": "str", "reason": "str"}}
  ],
  "follow_up_plan": [
    {{"provider": "str", "specialty": "str", "timeframe": "str", "reason": "str"}}
  ],
  "pcp_name": "str",
  "discharge_instructions": "str",
  "clinical_assessment": "str"
}}

Rules:
- Use empty string "" for missing text fields
- Use empty list [] for missing list fields
- For medications, set is_new/is_changed/is_stopped based on context
- Include ALL diagnoses mentioned anywhere in the note
- Include ALL medications, not just new ones
- "clinical_assessment" is the overall clinical reasoning, not the plan

DISCHARGE SUMMARY:
{note_text}"""

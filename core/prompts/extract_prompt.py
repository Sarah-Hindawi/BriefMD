EXTRACT_SYSTEM = "You are a clinical data extraction assistant. Return ONLY valid JSON. No explanation. No markdown."

EXTRACT_PROMPT = """Extract data from this discharge summary into JSON.
Return ONLY valid JSON matching this schema exactly.

JSON schema:
{{
  "chief_complaint": "str",
  "admission_diagnosis": "str",
  "discharge_diagnosis": "str",
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

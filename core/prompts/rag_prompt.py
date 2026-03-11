# RAG was dropped from this project. We have ~10 guidelines, not hundreds.
# Hardcoded checklist logic in checks/ is more reliable than vector search
# at this scale. Mistral 7B already knows clinical pharmacology.
# Patient-specific answers come from feeding patient data into the prompt,
# not retrieval. See core/agent.py ask() method.
#
# This file is intentionally empty. Do not add RAG prompts here.

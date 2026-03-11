"""
BriefMD Knowledge Layer
=======================
Clinical knowledge that grounds the pipeline's decisions.
All deterministic — no LLM calls in this package.
"""

from knowledge.hqo_checklist import run_hqo_checklist
from knowledge.drug_interactions import check_interactions, InteractionFlag
from knowledge.lab_ranges import LabRangeChecker, LabAlert

# REMOVED: pcp_preferences — both sides now use HQO checklist

__all__ = [
    "run_hqo_checklist",
    "check_interactions",
    "InteractionFlag",
    "LabRangeChecker",
    "LabAlert",
]


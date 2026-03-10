from __future__ import annotations

from pydantic import BaseModel, Field


class Node(BaseModel):
    icd9_code: str
    label: str
    is_dangerous: bool = False


class Edge(BaseModel):
    source: str  # icd9_code
    target: str  # icd9_code
    weight: int = 1
    is_dangerous: bool = False
    description: str = ""


class Cluster(BaseModel):
    name: str
    icd9_codes: list[str] = Field(default_factory=list)
    risk_note: str = ""


class SimilarPatient(BaseModel):
    subject_id: int
    hadm_id: int
    shared_codes: list[str] = Field(default_factory=list)
    similarity_score: float = 0.0


class ComorbidityNetwork(BaseModel):
    """Step 3 output: comorbidity graph built from patient ICD9 codes."""

    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    clusters: list[Cluster] = Field(default_factory=list)
    dangerous_edges: list[Edge] = Field(default_factory=list)
    similar_patients: list[SimilarPatient] = Field(default_factory=list)

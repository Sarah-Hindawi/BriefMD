"""
Chat Schemas — RAG Q&A
=======================
Request/response for the PCP's conversational interface.
"Why was metformin stopped?" → retrieves context → answers.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ChatMessage(BaseModel):
    role: str = Field(description="'user' or 'assistant'")
    content: str


class ChatRequest(BaseModel):
    """A question from the PCP about a specific patient."""
    hadm_id: int = Field(description="Patient context to scope the answer")
    question: str = Field(description="Natural language question from the PCP")
    conversation_history: list[ChatMessage] = Field(
        default_factory=list,
        description="Prior messages for multi-turn context"
    )


class ChatSource(BaseModel):
    """A retrieved chunk that contributed to the answer."""
    source_type: str = Field(description="'guideline', 'patient_data', 'checklist'")
    title: str
    excerpt: str = Field(description="Relevant snippet (truncated)")
    relevance_score: float


class ChatResponse(BaseModel):
    answer: str = Field(description="Generated answer grounded in retrieved context")
    sources: list[ChatSource] = Field(
        default_factory=list,
        description="Retrieved chunks that informed the answer"
    )
    confidence: Optional[str] = Field(
        default=None,
        description="'high', 'medium', 'low' — based on retrieval relevance"
    )


class AskResponse(BaseModel):
    hadm_id: int
    question: str
    answer: str
    sources: list[ChatSource] = Field(default_factory=list)
    confidence: Optional[str] = None
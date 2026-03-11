"""
BriefMD Retriever
=================
Adapter between agent.py and teammate's rag/vector_store.py.

Her code:
    upsert_case(case_id, text, metadata)      <- ingestion
    retrieve_similar(query, n_results=3)       <- returns list[dict]

Collection: discharge_summaries
Embedding: all-MiniLM-L6-v2 (384 dims, cosine)
Payload: case_id, admission_diagnosis, gender, age, text
Storage: local file persistence (qdrant_db/ folder)

This file:
    retriever.find_similar_cases(query, n)     <- agent.py calls this
    retriever.search_guidelines(query, n)      <- chat router calls this
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SimilarCase:
    case_id: str = ""
    score: float = 0.0
    text: str = ""
    admission_diagnosis: str = ""
    age: int = 0
    gender: str = ""
    metadata: dict = field(default_factory=dict)


class Retriever:
    """
    Wraps rag/vector_store.py for use by the agent and chat router.

    Initialize with the vector_store module's retrieve function.
    Falls back gracefully if Qdrant isn't running.
    """

    def __init__(self, vector_store_module=None):
        """
        Args:
            vector_store_module: The imported rag.vector_store module,
                or any object with a retrieve_similar(query, n_results) method.
        """
        self._vs = vector_store_module
        if self._vs is None:
            try:
                from rag import vector_store
                self._vs = vector_store
                logger.info("Retriever connected to rag.vector_store")
            except Exception as e:
                logger.warning(f"Could not import rag.vector_store: {e}")

    @property
    def available(self) -> bool:
        return self._vs is not None and hasattr(self._vs, "retrieve_similar")

    def find_similar_cases(
        self,
        query: str,
        n: int = 3,
    ) -> list[SimilarCase]:
        """
        Find similar patient cases. Called by agent.py for context enrichment.

        Args:
            query: Discharge summary text or clinical description.
            n: Number of similar cases to return.

        Returns:
            List of SimilarCase with text, diagnosis, demographics.
        """
        if not self.available:
            logger.warning("Retriever not available — returning empty results")
            return []

        try:
            raw_results = self._vs.retrieve_similar(query=query, n_results=n)

            cases = []
            for item in raw_results:
                cases.append(SimilarCase(
                    case_id=str(item.get("case_id", "")),
                    score=float(item.get("score", 0.0)),
                    text=item.get("text", ""),
                    admission_diagnosis=item.get("admission_diagnosis", ""),
                    age=int(item.get("age", 0)),
                    gender=item.get("gender", ""),
                    metadata=item,
                ))

            logger.info(f"Retrieved {len(cases)} similar cases")
            return cases

        except Exception as e:
            logger.error(f"Similar case retrieval failed: {e}")
            return []

    def search_guidelines(
        self,
        query: str,
        n: int = 3,
    ) -> list[dict]:
        """
        Search for relevant guideline context. Uses same vector store
        but could be a separate collection later.

        For now, reuses discharge_summaries collection — similar cases
        often contain relevant clinical patterns.
        """
        cases = self.find_similar_cases(query=query, n=n)
        return [
            {
                "text": c.text[:500],
                "source": "similar_case",
                "diagnosis": c.admission_diagnosis,
                "score": c.score,
            }
            for c in cases
        ]

    def build_rag_context(
        self,
        query: str,
        n: int = 3,
        max_chars: int = 3000,
    ) -> str:
        """
        Build a context string for the LLM prompt from retrieved cases.

        Used by agent.ask() and the /chat/ask endpoint:
            context = retriever.build_rag_context(question)
            llm.generate(prompt=f"Context:\\n{context}\\n\\nQuestion: {question}")

        Args:
            query: The question or clinical text to search with.
            n: Number of cases to retrieve.
            max_chars: Maximum total characters in the context string.

        Returns:
            Formatted string of similar cases for prompt injection.
        """
        cases = self.find_similar_cases(query=query, n=n)

        if not cases:
            return "No similar cases found in the database."

        parts = []
        total = 0
        for i, case in enumerate(cases, 1):
            snippet = (
                f"[Similar Case {i}] "
                f"Diagnosis: {case.admission_diagnosis} | "
                f"Age: {case.age}, Gender: {case.gender}\n"
                f"{case.text[:800]}"
            )
            if total + len(snippet) > max_chars:
                break
            parts.append(snippet)
            total += len(snippet)

        return "\n\n".join(parts)

"""
BriefMD Vector Store
====================
Abstraction layer over the vector database.
Your teammate built Qdrant. This wraps her code so the agent
doesn't need to know which vector DB is underneath.

The agent calls:
    results = vector_store.find_similar_cases(query_text, n=5)
    results = vector_store.search_guidelines(query_text, n=3)

That's it. Everything below is wiring.

STATUS: Adapter ready. Wire to teammate's Qdrant code once you
        know her collection names and query functions.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SimilarCase:
    """A similar patient case retrieved from the vector store."""
    hadm_id: int = 0
    score: float = 0.0           # Similarity score (higher = more similar)
    summary_snippet: str = ""     # Relevant text chunk
    admission_diagnosis: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class GuidelineChunk:
    """A retrieved chunk from clinical guidelines."""
    text: str = ""
    source: str = ""             # "HQO", "drug_interaction", "clinical_guideline"
    score: float = 0.0
    metadata: dict = field(default_factory=dict)


class VectorStore:
    """
    Wraps the Qdrant vector database.

    Initialize once at startup. The agent and chat router call
    find_similar_cases() and search_guidelines().
    """

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        cases_collection: str = "clinical_cases",
        guidelines_collection: str = "guidelines",
    ):
        """
        Args:
            qdrant_url: Qdrant server URL (local Docker or Qdrant Cloud).
            cases_collection: Collection name for patient case embeddings.
            guidelines_collection: Collection name for guideline chunks.
        """
        self.qdrant_url = qdrant_url
        self.cases_collection = cases_collection
        self.guidelines_collection = guidelines_collection
        self._client = None
        self._embedder = None

        try:
            from qdrant_client import QdrantClient
            self._client = QdrantClient(url=qdrant_url)
            logger.info(f"Connected to Qdrant at {qdrant_url}")
        except ImportError:
            logger.warning("qdrant-client not installed. pip install qdrant-client")
        except Exception as e:
            logger.warning(f"Could not connect to Qdrant at {qdrant_url}: {e}")

        # Initialize embedding model
        # Your teammate likely used one of these:
        try:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Embedding model loaded: all-MiniLM-L6-v2")
        except ImportError:
            try:
                # Qdrant's built-in fast embeddings
                from fastembed import TextEmbedding
                self._embedder = TextEmbedding("BAAI/bge-small-en-v1.5")
                logger.info("Embedding model loaded: fastembed BGE-small")
            except ImportError:
                logger.warning(
                    "No embedding model available. "
                    "pip install sentence-transformers OR pip install fastembed"
                )

    @property
    def available(self) -> bool:
        return self._client is not None and self._embedder is not None

    # -----------------------------------------------------------------------
    # Public API — this is what the agent calls
    # -----------------------------------------------------------------------

    def find_similar_cases(
        self,
        query_text: str,
        n: int = 5,
        score_threshold: float = 0.3,
    ) -> list[SimilarCase]:
        """
        Find patient cases similar to the query text.

        Used by the agent to give the LLM domain context:
        "In similar patients, X% had complication Y."

        Args:
            query_text: Discharge summary or clinical description.
            n: Number of similar cases to return.
            score_threshold: Minimum similarity score (0-1).

        Returns:
            List of SimilarCase objects, sorted by relevance.
        """
        if not self.available:
            logger.warning("Vector store not available — returning empty results")
            return []

        try:
            embedding = self._embed(query_text)

            from qdrant_client.models import models
            results = self._client.query_points(
                collection_name=self.cases_collection,
                query=embedding,
                limit=n,
                score_threshold=score_threshold,
            )

            cases = []
            for point in results.points:
                payload = point.payload or {}
                cases.append(SimilarCase(
                    hadm_id=payload.get("hadm_id", 0),
                    score=point.score,
                    summary_snippet=payload.get("text", payload.get("summary", "")),
                    admission_diagnosis=payload.get("admission_diagnosis", ""),
                    metadata=payload,
                ))

            logger.info(f"Found {len(cases)} similar cases for query (len={len(query_text)})")
            return cases

        except Exception as e:
            logger.error(f"Similar case search failed: {e}")
            return []

    def search_guidelines(
        self,
        query_text: str,
        n: int = 5,
        source_filter: Optional[str] = None,
    ) -> list[GuidelineChunk]:
        """
        Search clinical guidelines for relevant context.

        Used by the RAG pipeline to ground LLM answers in guidelines.

        Args:
            query_text: The question or topic to search for.
            n: Number of chunks to return.
            source_filter: Filter by source type ("HQO", "drug_interaction", etc.)

        Returns:
            List of GuidelineChunk objects, sorted by relevance.
        """
        if not self.available:
            logger.warning("Vector store not available — returning empty results")
            return []

        try:
            embedding = self._embed(query_text)

            query_filter = None
            if source_filter:
                from qdrant_client.models import models
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source",
                            match=models.MatchValue(value=source_filter),
                        )
                    ]
                )

            results = self._client.query_points(
                collection_name=self.guidelines_collection,
                query=embedding,
                query_filter=query_filter,
                limit=n,
            )

            chunks = []
            for point in results.points:
                payload = point.payload or {}
                chunks.append(GuidelineChunk(
                    text=payload.get("text", ""),
                    source=payload.get("source", "unknown"),
                    score=point.score,
                    metadata=payload,
                ))

            logger.info(f"Found {len(chunks)} guideline chunks for query")
            return chunks

        except Exception as e:
            logger.error(f"Guideline search failed: {e}")
            return []

    # -----------------------------------------------------------------------
    # Private
    # -----------------------------------------------------------------------

    def _embed(self, text: str) -> list[float]:
        """Convert text to embedding vector."""
        if hasattr(self._embedder, "encode"):
            # sentence-transformers
            return self._embedder.encode(text).tolist()
        elif hasattr(self._embedder, "embed"):
            # fastembed
            embeddings = list(self._embedder.embed([text]))
            return embeddings[0].tolist()
        else:
            raise RuntimeError(f"Unknown embedder type: {type(self._embedder)}")
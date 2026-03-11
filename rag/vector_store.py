from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from sentence_transformers import SentenceTransformer

COLLECTION  = "discharge_summaries"
VECTOR_SIZE = 384

client   = QdrantClient(path="./qdrant_db")
embedder = SentenceTransformer("all-MiniLM-L6-v2")


def _ensure_collection():
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def upsert_case(case_id: str, text: str, metadata: dict):
    _ensure_collection()
    embedding = embedder.encode(text).tolist()
    clean_meta = {
        k: (v if isinstance(v, (str, int, float, bool)) else str(v))
        for k, v in metadata.items()
    }
    client.upsert(
        collection_name=COLLECTION,
        points=[
            PointStruct(
                id=abs(hash(case_id)) % (2**53),
                vector=embedding,
                payload={**clean_meta, "text": text},
            )
        ],
    )


def retrieve_similar(query: str, n_results: int = 3) -> list[dict]:
    _ensure_collection()
    embedding = embedder.encode(query).tolist()
    results = client.search(
        collection_name=COLLECTION,
        query_vector=embedding,
        limit=n_results,
    )
    return [
        {
            "case_id":             r.payload.get("case_id"),
            "admission_diagnosis": r.payload.get("admission_diagnosis"),
            "gender":              r.payload.get("gender"),
            "age":                 r.payload.get("age"),
            "score":               round(r.score, 3),
        }
        for r in results
    ]
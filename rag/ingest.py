import os
import pandas as pd
from huggingface_hub import hf_hub_download
from dotenv import load_dotenv
from vector_store import upsert_case

load_dotenv()

repo_id = "bavehackathon/2026-healthcare-ai"


def ingest():
    path = hf_hub_download(
        repo_id=repo_id,
        filename="clinical_cases.csv.gz",
        repo_type="dataset",
        token=os.getenv("HF_TOKEN"),
    )
    df = pd.read_csv(path)

    print(f"Ingesting {len(df)} cases into ChromaDB.")

    for _, row in df.iterrows():
        upsert_case(
            case_id=str(row["case_id"]),
            text=row["discharge_summary"],
            metadata={
                "case_id": str(row["case_id"]),
                "age": int(row["age"]),
                "gender": str(row["gender"]),
                "admission_diagnosis": str(row["admission_diagnosis"]),
            },
        )

    print(f"\nIngesting completed. {len(df)} cases stored in ChromaDB.")


if __name__ == "__main__":
    ingest()
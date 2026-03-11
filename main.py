import os
import pandas as pd
from huggingface_hub import hf_hub_download
from agents.sentinel import run as sentinel
from agents.synopsis import run as synopsis
from rag.vector_store import retrieve_similar

hf_token = os.get('HF_TOKEN')

if not hf_token:
    print("Warning: HF_TOKEN not found in environment variables.")

repo_id = "bavehackathon/2026-healthcare-ai"

def process_patient(case_id: str):
    df = pd.read_csv(
    hf_hub_download(repo_id=repo_id, filename="clinical_cases.csv.gz", repo_type="dataset")
    )

    patient = df[df["case_id"] == case_id].iloc[0]

    print(f"\nRunning SENTINEL for {case_id}...")
    flags = sentinel(case_id)
    print(f"    {len(flags)} anomalies flagged")

    print(f"Running sentinel...")
    briefing = synopsis(patient["discharge_summary"], flags)
    print("\n--- BRIEF MD OUTPUT ---")
    print(briefing)

    print("\nSimilar cases from vector store:")
    results = retrieve_similar(patient["admission_diagnosis"])
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        print(f"  - {meta['admission_diagnosis']} | {meta['gender']}, {meta['age']}yo")

if __name__ == "__main__":
    process_patient("CASE_00001")
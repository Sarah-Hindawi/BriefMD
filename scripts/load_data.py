"""Download 6 CSVs from HuggingFace to data/datasets/."""

import sys
from pathlib import Path

# Allow running as standalone script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.logging import setup_logging
from data.loader import load_from_huggingface

if __name__ == "__main__":
    setup_logging()
    bundle = load_from_huggingface()
    print(f"\nDone. Loaded {len(bundle.clinical_cases)} clinical cases.")
    print(f"  Diagnoses:     {len(bundle.diagnoses)} rows")
    print(f"  Diagnosis dict:{len(bundle.diagnosis_dict)} rows")
    print(f"  Labs:          {len(bundle.labs)} rows")
    print(f"  Lab dict:      {len(bundle.lab_dict)} rows")
    print(f"  Prescriptions: {len(bundle.prescriptions)} rows")

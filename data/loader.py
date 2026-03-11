"""Load 6 CSVs from HuggingFace dataset into pandas DataFrames."""

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from config.settings import settings

logger = logging.getLogger(__name__)

REPO_ID = "bavehackathon/2026-healthcare-ai"

FILES = {
    "clinical_cases": "clinical_cases.csv.gz",
    "diagnoses": "diagnoses_subset.csv.gz",
    "diagnosis_dict": "diagnosis_dictionary.csv.gz",
    "labs": "labs_subset.csv.gz",
    "lab_dict": "lab_dictionary.csv.gz",
    "prescriptions": "prescriptions_subset.csv.gz",
}


@dataclass
class DataBundle:
    clinical_cases: pd.DataFrame
    diagnoses: pd.DataFrame
    diagnosis_dict: pd.DataFrame
    labs: pd.DataFrame
    lab_dict: pd.DataFrame
    prescriptions: pd.DataFrame


def load_from_local(data_dir: Path | None = None) -> DataBundle:
    """Load CSVs from local disk."""
    data_dir = data_dir or settings.data_dir

    bundle = {}
    for key, filename in FILES.items():
        path = data_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing dataset file: {path}. Run 'make data' first.")
        logger.info(f"Loading {filename}")
        bundle[key] = pd.read_csv(path)

    logger.info(
        f"Loaded {len(bundle)} tables: "
        + ", ".join(f"{k}={len(v)} rows" for k, v in bundle.items())
    )
    return DataBundle(**bundle)


def load_from_huggingface(data_dir: Path | None = None) -> DataBundle:
    """Download CSVs from HuggingFace and load into DataFrames."""
    from huggingface_hub import hf_hub_download

    data_dir = data_dir or settings.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    bundle = {}
    for key, filename in FILES.items():
        local_path = data_dir / filename
        if local_path.exists():
            logger.info(f"Already downloaded: {filename}")
        else:
            logger.info(f"Downloading {filename} from {REPO_ID}")
            downloaded = hf_hub_download(
                repo_id=REPO_ID,
                filename=filename,
                repo_type="dataset",
                local_dir=str(data_dir),
            )
            local_path = Path(downloaded)

        bundle[key] = pd.read_csv(local_path)

    logger.info(
        f"Loaded {len(bundle)} tables: "
        + ", ".join(f"{k}={len(v)} rows" for k, v in bundle.items())
    )
    return DataBundle(**bundle)

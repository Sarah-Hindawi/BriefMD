"""Co-occurrence matrix and similar patient finder from the full diagnoses table."""

import logging
from collections import Counter

import pandas as pd

logger = logging.getLogger(__name__)


def build_cooccurrence_matrix(diagnoses: pd.DataFrame) -> pd.DataFrame:
    """Build a symmetric co-occurrence matrix from all patient diagnoses.

    Each cell (A, B) = number of admissions where both ICD9 codes appear.
    """
    if diagnoses.empty or "icd9_code" not in diagnoses.columns:
        return pd.DataFrame()

    grouped = diagnoses.groupby("hadm_id")["icd9_code"].apply(
        lambda x: list(x.astype(str).str.strip().unique())
    )

    pair_counts: Counter[tuple[str, str]] = Counter()
    for codes in grouped:
        for i, a in enumerate(codes):
            for b in codes[i + 1 :]:
                key = (min(a, b), max(a, b))
                pair_counts[key] += 1

    if not pair_counts:
        return pd.DataFrame()

    rows = [
        {"code_a": a, "code_b": b, "count": count}
        for (a, b), count in pair_counts.items()
    ]

    matrix = pd.DataFrame(rows).sort_values("count", ascending=False).reset_index(drop=True)
    logger.info(f"Co-occurrence matrix: {len(matrix)} pairs from {len(grouped)} admissions")
    return matrix


def get_top_pairs(
    diagnoses: pd.DataFrame,
    diagnosis_dict: pd.DataFrame | None = None,
    top_n: int = 20,
) -> list[dict]:
    """Return the top N most common co-occurring diagnosis pairs with labels."""
    matrix = build_cooccurrence_matrix(diagnoses)
    if matrix.empty:
        return []

    top = matrix.head(top_n)

    code_map: dict[str, str] = {}
    if diagnosis_dict is not None and not diagnosis_dict.empty:
        title_col = "short_title" if "short_title" in diagnosis_dict.columns else "long_title"
        code_map = dict(zip(
            diagnosis_dict["icd9_code"].astype(str).str.strip(),
            diagnosis_dict[title_col].astype(str),
        ))

    return [
        {
            "code_a": row["code_a"],
            "code_b": row["code_b"],
            "label_a": code_map.get(row["code_a"], row["code_a"]),
            "label_b": code_map.get(row["code_b"], row["code_b"]),
            "count": int(row["count"]),
        }
        for _, row in top.iterrows()
    ]


def find_similar_patients(
    target_codes: list[str],
    diagnoses: pd.DataFrame,
    exclude_hadm_id: int | None = None,
    top_n: int = 10,
) -> list[dict]:
    """Find patients with the most shared ICD9 codes."""
    if diagnoses.empty or not target_codes:
        return []

    target_set = {c.strip() for c in target_codes}

    grouped = diagnoses.groupby(["subject_id", "hadm_id"])["icd9_code"].apply(
        lambda x: set(x.astype(str).str.strip())
    )

    results: list[dict] = []
    for (subject_id, hadm_id), codes in grouped.items():
        if hadm_id == exclude_hadm_id:
            continue

        shared = target_set & codes
        if len(shared) < 2:
            continue

        results.append({
            "subject_id": int(subject_id),
            "hadm_id": int(hadm_id),
            "shared_codes": sorted(shared),
            "shared_count": len(shared),
            "similarity": round(len(shared) / max(len(target_set), len(codes)), 3),
        })

    results.sort(key=lambda r: r["similarity"], reverse=True)
    return results[:top_n]

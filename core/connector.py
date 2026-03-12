import logging

import networkx as nx
import pandas as pd

from core.models.network import (
    Cluster,
    ComorbidityNetwork,
    Edge,
    Node,
    SimilarPatient,
)

logger = logging.getLogger(__name__)

KNOWN_DANGEROUS = {
    ("4019", "41401"): "Hypertension + CAD (228 patients)",
    ("4019", "42731"): "Hypertension + AFib (219 patients)",
    ("42731", "4280"): "AFib + Heart Failure (198 patients)",
    ("4019", "4280"): "Hypertension + CHF (188 patients)",
    ("25000", "4019"): "Diabetes + Hypertension (181 patients)",
    ("4280", "5849"): "Heart Failure + AKI (137 patients)",
    ("25000", "5849"): "Diabetes + AKI (metformin risk)",
}


# Fallback for codes missing from the diagnosis dictionary entirely
_MISSING_CODE_NAMES = {
    "1732": "Malignant melanoma of ear",
    "1733": "Malignant melanoma of face NEC",
    "1734": "Malignant melanoma of scalp/neck",
    "1735": "Malignant melanoma of trunk",
    "3337": "Sympathetic reflex dystrophy",
    "4251": "Hypertrophic obstructive cardiomyopathy",
    "4440": "Atherosclerosis of extremities",
    "4881": "Legionnaires disease",
    "5996": "Urinary obstruction",
    "7473": "Essential hemorrhage",
    "7671": "Fetal death from asphyxia",
    "7687": "Abnormal fetal heart rate/rhythm",
    "7775": "Neonatal bradycardia",
    "7793": "Feeding difficulties",
    "9697": "Late effect of radiation",
    "9708": "Other radiation sickness",
    "9952": "Adverse effect of drug, unspecified",
    "9995": "Child maltreatment syndrome",
    "V721": "Exam of ears and hearing",
}


class Connector:
    """Step 3: Build comorbidity network from ICD9 codes. No LLM."""

    def __init__(self, all_diagnoses: pd.DataFrame, diagnosis_dict: pd.DataFrame) -> None:
        self.all_diagnoses = all_diagnoses
        self._icd9_lookup = self._build_icd9_lookup(diagnosis_dict)
        self.cooccurrence = self._build_cooccurrence()

    def connect(
        self,
        patient_codes: list[str],
        hadm_id: int | None = None,
    ) -> ComorbidityNetwork:
        G = self._build_graph(patient_codes)

        nodes = [
            Node(
                icd9_code=n,
                label=self._lookup_name(n),
                is_dangerous=self._is_dangerous_node(n, patient_codes),
            )
            for n in G.nodes
        ]

        edges: list[Edge] = []
        dangerous_edges: list[Edge] = []
        for u, v, data in G.edges(data=True):
            pair_key = self._pair_key(u, v)
            is_dangerous = pair_key in KNOWN_DANGEROUS
            edge = Edge(
                source=u,
                target=v,
                weight=data.get("weight", 1),
                is_dangerous=is_dangerous,
                description=KNOWN_DANGEROUS.get(pair_key, ""),
            )
            edges.append(edge)
            if is_dangerous:
                dangerous_edges.append(edge)

        clusters = self._find_clusters(G)
        similar = self._find_similar_patients(patient_codes, hadm_id)

        logger.info(
            f"Network built: {len(nodes)} nodes, {len(edges)} edges, "
            f"{len(dangerous_edges)} dangerous, {len(clusters)} clusters"
        )

        return ComorbidityNetwork(
            nodes=nodes,
            edges=edges,
            clusters=clusters,
            dangerous_edges=dangerous_edges,
            similar_patients=similar,
        )

    def _build_icd9_lookup(self, diagnosis_dict: pd.DataFrame) -> dict[str, str]:
        """Build ICD-9 lookup with both dotted and undotted code variants."""
        if diagnosis_dict.empty:
            return {}

        lookup: dict[str, str] = {}
        for _, row in diagnosis_dict.iterrows():
            code = str(row.get("icd9_code", "")).strip()
            name = str(row.get("long_title", row.get("short_title", "")))
            if code and name:
                lookup[code] = name
                lookup[code.replace(".", "")] = name

        return lookup

    def _lookup_name(self, code: str) -> str:
        """Resolve ICD-9 code to human-readable name with fuzzy fallbacks."""
        code = str(code).strip()

        # 1. Exact match
        if code in self._icd9_lookup:
            return self._icd9_lookup[code]

        # 2. Try common suffixes (0, 1, 9)
        for suffix in ("0", "1", "9"):
            if code + suffix in self._icd9_lookup:
                return self._icd9_lookup[code + suffix]

        # 3. Try truncating last digit (child -> parent)
        if len(code) > 3 and code[:-1] in self._icd9_lookup:
            return self._icd9_lookup[code[:-1]]

        # 4. Prefix scan — first dictionary code starting with this
        for dict_code, name in self._icd9_lookup.items():
            if dict_code.startswith(code) or code.startswith(dict_code):
                return name

        # 5. Hardcoded fallback for codes missing from dictionary
        if code in _MISSING_CODE_NAMES:
            return _MISSING_CODE_NAMES[code]

        # 6. Give up — return raw code
        return code

    def _build_cooccurrence(self) -> dict[tuple[str, str], int]:
        if self.all_diagnoses.empty:
            return {}

        cooc: dict[tuple[str, str], int] = {}
        grouped = self.all_diagnoses.groupby("hadm_id")["icd9_code"].apply(
            lambda x: list(x.astype(str).str.strip())
        )

        for codes in grouped:
            for i, a in enumerate(codes):
                for b in codes[i + 1 :]:
                    key = self._pair_key(a, b)
                    cooc[key] = cooc.get(key, 0) + 1

        return cooc

    def _build_graph(self, patient_codes: list[str]) -> nx.Graph:
        G = nx.Graph()
        codes = [c.strip() for c in patient_codes]

        for code in codes:
            G.add_node(code)

        for i, a in enumerate(codes):
            for b in codes[i + 1 :]:
                key = self._pair_key(a, b)
                weight = self.cooccurrence.get(key, 0)
                if weight > 0:
                    G.add_edge(a, b, weight=weight)

        return G

    def _find_clusters(self, G: nx.Graph) -> list[Cluster]:
        clusters: list[Cluster] = []

        for component in nx.connected_components(G):
            if len(component) < 2:
                continue

            codes = sorted(component)
            labels = [self._lookup_name(c) for c in codes]

            risk_notes: list[str] = []
            for i, a in enumerate(codes):
                for b in codes[i + 1 :]:
                    key = self._pair_key(a, b)
                    if key in KNOWN_DANGEROUS:
                        risk_notes.append(KNOWN_DANGEROUS[key])

            clusters.append(Cluster(
                name=" + ".join(labels[:4]) + ("..." if len(labels) > 4 else ""),
                icd9_codes=codes,
                risk_note="; ".join(risk_notes) if risk_notes else "",
            ))

        return clusters

    def _find_similar_patients(
        self,
        patient_codes: list[str],
        exclude_hadm_id: int | None = None,
    ) -> list[SimilarPatient]:
        if self.all_diagnoses.empty:
            return []

        patient_set = {c.strip() for c in patient_codes}
        grouped = self.all_diagnoses.groupby(["subject_id", "hadm_id"])["icd9_code"].apply(
            lambda x: set(x.astype(str).str.strip())
        )

        scored: list[SimilarPatient] = []
        for (subject_id, hadm_id), codes in grouped.items():
            if hadm_id == exclude_hadm_id:
                continue

            shared = patient_set & codes
            if len(shared) < 2:
                continue

            score = len(shared) / max(len(patient_set), len(codes))
            scored.append(SimilarPatient(
                subject_id=int(subject_id),
                hadm_id=int(hadm_id),
                shared_codes=sorted(shared),
                similarity_score=round(score, 3),
            ))

        scored.sort(key=lambda p: p.similarity_score, reverse=True)
        return scored[:10]

    def _is_dangerous_node(self, code: str, all_codes: list[str]) -> bool:
        return any(
            self._pair_key(code, other) in KNOWN_DANGEROUS
            for other in all_codes
            if other != code
        )

    @staticmethod
    def _pair_key(a: str, b: str) -> tuple[str, str]:
        return (min(a, b), max(a, b))

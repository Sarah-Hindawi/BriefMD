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


class Connector:
    """Step 3: Build comorbidity network from ICD9 codes. No LLM."""

    def __init__(self, all_diagnoses: pd.DataFrame, diagnosis_dict: pd.DataFrame) -> None:
        self.all_diagnoses = all_diagnoses
        self.code_to_title = self._build_code_map(diagnosis_dict)
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
                label=self.code_to_title.get(n, n),
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

    def _build_code_map(self, diagnosis_dict: pd.DataFrame) -> dict[str, str]:
        if diagnosis_dict.empty:
            return {}

        code_col = "icd9_code"
        title_col = "short_title" if "short_title" in diagnosis_dict.columns else "long_title"

        if code_col not in diagnosis_dict.columns or title_col not in diagnosis_dict.columns:
            return {}

        return dict(zip(
            diagnosis_dict[code_col].astype(str).str.strip(),
            diagnosis_dict[title_col].astype(str),
        ))

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
            labels = [self.code_to_title.get(c, c) for c in codes]

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

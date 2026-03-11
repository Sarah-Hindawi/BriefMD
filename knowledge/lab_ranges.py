"""
Lab Reference Ranges — Statistical Derivation
==============================================
Computes reference ranges from the dataset using 5th/95th percentiles.

WHY this approach:
- Clinically legitimate: reference ranges ARE statistical constructs
  (central 95% of a population is the standard method)
- Data-driven: derived from ~2000 real patient admissions
- Defensible: you can explain to judges exactly how you got them
- Not hardcoded: adapts to whatever dataset you load

Also includes a small override table for critical labs where
population-derived ranges might be misleading (e.g., troponin
should always be <0.04, regardless of dataset distribution).

Usage:
    from knowledge.lab_ranges import LabRangeChecker
    checker = LabRangeChecker(bundle.labs, bundle.lab_dict)
    alerts = checker.check_patient_labs(patient_labs_df)
"""

import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class LabRange:
    """Reference range for a single lab test."""
    itemid: int
    lab_name: str
    unit: str
    low: float
    high: float
    source: str  # "statistical" or "clinical_override"


@dataclass
class LabAlert:
    """A lab value outside the reference range."""
    lab_name: str
    value: float
    unit: str
    ref_low: float
    ref_high: float
    severity: str  # "critical" or "warning"
    direction: str  # "high" or "low"
    detail: str


# ---------------------------------------------------------------------------
# Clinical overrides for critical labs
# ---------------------------------------------------------------------------
# These labs have clinically defined thresholds that should NOT be derived
# from population statistics (because sick ICU patients skew the distribution).
#
# Format: itemid → (low, high, unit, severity_if_abnormal)
# itemids from MIMIC d_labitems — verify against your lab_dictionary.csv
# ---------------------------------------------------------------------------

CRITICAL_OVERRIDES: dict[int, dict] = {
    # Troponin T — any elevation is significant
    50911: {"low": 0.0, "high": 0.04, "unit": "ng/mL",
            "severity": "critical", "name": "Troponin T"},
    # Troponin I
    51003: {"low": 0.0, "high": 0.04, "unit": "ng/mL",
            "severity": "critical", "name": "Troponin I"},
    # Potassium — narrow critical range
    50971: {"low": 3.5, "high": 5.0, "unit": "mEq/L",
            "severity": "critical", "name": "Potassium"},
    # Sodium — narrow critical range
    50983: {"low": 136.0, "high": 145.0, "unit": "mEq/L",
            "severity": "critical", "name": "Sodium"},
    # Glucose — hypoglycemia is dangerous
    50931: {"low": 70.0, "high": 200.0, "unit": "mg/dL",
            "severity": "warning", "name": "Glucose"},
    # Creatinine
    50912: {"low": 0.5, "high": 1.3, "unit": "mg/dL",
            "severity": "warning", "name": "Creatinine"},
    # BUN
    51006: {"low": 6.0, "high": 24.0, "unit": "mg/dL",
            "severity": "warning", "name": "BUN"},
    # Hemoglobin
    51222: {"low": 11.0, "high": 17.0, "unit": "g/dL",
            "severity": "warning", "name": "Hemoglobin"},
    # Platelets
    51265: {"low": 150.0, "high": 400.0, "unit": "K/uL",
            "severity": "warning", "name": "Platelets"},
    # WBC
    51301: {"low": 4.0, "high": 11.0, "unit": "K/uL",
            "severity": "warning", "name": "WBC"},
    # INR
    51237: {"low": 0.8, "high": 1.2, "unit": "",
            "severity": "warning", "name": "INR"},
    # Lactate — elevated = tissue hypoperfusion
    50813: {"low": 0.5, "high": 2.0, "unit": "mmol/L",
            "severity": "critical", "name": "Lactate"},
}


# ---------------------------------------------------------------------------
# LabRangeChecker
# ---------------------------------------------------------------------------


class LabRangeChecker:
    """
    Builds reference ranges from dataset statistics, with clinical overrides
    for critical labs. Then checks individual patient labs against these ranges.
    """

    def __init__(
        self,
        all_labs: pd.DataFrame,
        lab_dict: pd.DataFrame,
        percentile_low: float = 0.05,
        percentile_high: float = 0.95,
        min_samples: int = 30,
    ):
        """
        Args:
            all_labs: Full labs table from DataBundle (all patients)
            lab_dict: Lab dictionary mapping itemid → lab_name
            percentile_low: Lower percentile for reference range (default 5th)
            percentile_high: Upper percentile for reference range (default 95th)
            min_samples: Minimum observations needed to compute a range
        """
        self.ranges: dict[int, LabRange] = {}
        self._build_ranges(all_labs, lab_dict, percentile_low, percentile_high, min_samples)
        logger.info(f"LabRangeChecker initialized with {len(self.ranges)} lab ranges")

    def _build_ranges(
        self,
        all_labs: pd.DataFrame,
        lab_dict: pd.DataFrame,
        pct_low: float,
        pct_high: float,
        min_samples: int,
    ) -> None:
        """Compute statistical reference ranges from the full dataset."""
        if all_labs.empty:
            logger.warning("Empty labs table — no ranges computed")
            return

        # Build name lookup
        name_map: dict[int, str] = {}
        unit_map: dict[int, str] = {}
        if not lab_dict.empty:
            name_map = dict(zip(
                lab_dict["itemid"].astype(int),
                lab_dict["lab_name"].astype(str),
            ))

        # Convert values to numeric, dropping non-numeric
        labs = all_labs.copy()
        labs["value_num"] = pd.to_numeric(labs["value"], errors="coerce")
        labs = labs.dropna(subset=["value_num"])

        # Get unit per itemid (most common)
        if "unit" in labs.columns:
            unit_map = (
                labs.groupby("itemid")["unit"]
                .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else "")
                .to_dict()
            )

        # Group by itemid and compute percentiles
        grouped = labs.groupby("itemid")["value_num"]

        for itemid, group in grouped:
            itemid = int(itemid)

            # Clinical override takes priority
            if itemid in CRITICAL_OVERRIDES:
                override = CRITICAL_OVERRIDES[itemid]
                self.ranges[itemid] = LabRange(
                    itemid=itemid,
                    lab_name=override.get("name", name_map.get(itemid, f"Lab {itemid}")),
                    unit=override.get("unit", unit_map.get(itemid, "")),
                    low=override["low"],
                    high=override["high"],
                    source="clinical_override",
                )
                continue

            # Need enough samples for statistical validity
            if len(group) < min_samples:
                continue

            low_val = float(group.quantile(pct_low))
            high_val = float(group.quantile(pct_high))

            # Sanity check: low should be less than high
            if low_val >= high_val:
                continue

            self.ranges[itemid] = LabRange(
                itemid=itemid,
                lab_name=name_map.get(itemid, f"Lab {itemid}"),
                unit=unit_map.get(itemid, ""),
                low=round(low_val, 2),
                high=round(high_val, 2),
                source="statistical",
            )

        logger.info(
            f"Computed ranges: {sum(1 for r in self.ranges.values() if r.source == 'clinical_override')} "
            f"clinical overrides + "
            f"{sum(1 for r in self.ranges.values() if r.source == 'statistical')} "
            f"statistical"
        )

    def check_patient_labs(
        self,
        patient_labs: pd.DataFrame,
        use_latest_only: bool = True,
    ) -> list[LabAlert]:
        """
        Check a patient's lab values against reference ranges.

        Args:
            patient_labs: Patient's labs DataFrame (from PatientContext.labs)
            use_latest_only: If True, only check the most recent value per lab test.
                           This avoids flagging old values that were normal on admission
                           but abnormal earlier.

        Returns:
            List of LabAlert for values outside reference ranges.
        """
        if patient_labs.empty or not self.ranges:
            return []

        labs = patient_labs.copy()
        labs["value_num"] = pd.to_numeric(labs["value"], errors="coerce")
        labs = labs.dropna(subset=["value_num"])

        if labs.empty:
            return []

        # Use latest value per lab test
        if use_latest_only and "charttime" in labs.columns:
            labs = labs.sort_values("charttime").groupby("itemid").last().reset_index()

        alerts: list[LabAlert] = []

        for _, row in labs.iterrows():
            itemid = int(row["itemid"])
            if itemid not in self.ranges:
                continue

            ref = self.ranges[itemid]
            value = float(row["value_num"])

            # Determine severity from clinical overrides
            override = CRITICAL_OVERRIDES.get(itemid)
            base_severity = override["severity"] if override else "warning"

            if value < ref.low:
                alerts.append(LabAlert(
                    lab_name=ref.lab_name,
                    value=round(value, 2),
                    unit=ref.unit,
                    ref_low=ref.low,
                    ref_high=ref.high,
                    severity=base_severity,
                    direction="low",
                    detail=(
                        f"{ref.lab_name} = {round(value, 2)} {ref.unit} "
                        f"(ref: {ref.low}–{ref.high}). Below reference range."
                    ),
                ))
            elif value > ref.high:
                alerts.append(LabAlert(
                    lab_name=ref.lab_name,
                    value=round(value, 2),
                    unit=ref.unit,
                    ref_low=ref.low,
                    ref_high=ref.high,
                    severity=base_severity,
                    direction="high",
                    detail=(
                        f"{ref.lab_name} = {round(value, 2)} {ref.unit} "
                        f"(ref: {ref.low}–{ref.high}). Above reference range."
                    ),
                ))

        # Sort: critical first, then by how far outside range
        alerts.sort(key=lambda a: (0 if a.severity == "critical" else 1, a.lab_name))

        logger.info(
            f"Lab check: {len(labs)} values checked, "
            f"{len(alerts)} abnormal "
            f"({sum(1 for a in alerts if a.severity == 'critical')} critical)"
        )
        return alerts

    def get_abnormal_not_in_note(
        self,
        patient_labs: pd.DataFrame,
        labs_mentioned_in_note: list[str],
    ) -> list[LabAlert]:
        """
        Find abnormal labs that the discharge note does NOT mention.

        This is a key flag for the ED quality gate:
        "You have 3 critical lab values that aren't referenced in the note."

        Args:
            patient_labs: Patient's labs DataFrame
            labs_mentioned_in_note: Lab names extracted from the discharge note by LLM

        Returns:
            LabAlerts for abnormal values not mentioned in the note.
        """
        all_abnormal = self.check_patient_labs(patient_labs)
        if not all_abnormal or not labs_mentioned_in_note:
            return all_abnormal  # If note mentions nothing, flag everything

        # Normalize mentioned lab names for fuzzy matching
        mentioned_lower = {name.lower().strip() for name in labs_mentioned_in_note}

        not_mentioned = []
        for alert in all_abnormal:
            lab_lower = alert.lab_name.lower().strip()
            # Check if any mentioned lab name is a substring match
            is_mentioned = any(
                lab_lower in m or m in lab_lower
                for m in mentioned_lower
            )
            if not is_mentioned:
                not_mentioned.append(alert)

        logger.info(
            f"Abnormal labs not in note: {len(not_mentioned)} of {len(all_abnormal)} "
            f"(note mentions {len(labs_mentioned_in_note)} labs)"
        )
        return not_mentioned
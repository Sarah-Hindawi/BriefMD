RANGES = {
    "wbc":        {"low": 4.5,  "high": 11.0, "unit": "K/uL"},
    "hemoglobin": {"low": 12.0, "high": 17.5, "unit": "g/dL"},
    "hematocrit": {"low": 36,   "high": 52,   "unit": "%"},
    "platelets":  {"low": 150,  "high": 400,  "unit": "K/uL"},
    "sodium":     {"low": 136,  "high": 145,  "unit": "mEq/L"},
    "potassium":  {"low": 3.5,  "high": 5.1,  "unit": "mEq/L"},
    "creatinine": {"low": 0.6,  "high": 1.2,  "unit": "mg/dL"},
    "glucose":    {"low": 70,   "high": 100,  "unit": "mg/dL"},
    "inr":        {"low": 0.8,  "high": 1.1,  "unit": ""},
    "troponin":   {"low": 0,    "high": 0.04, "unit": "ng/mL"},
}

def interpret(name: str, value: float) -> str:
    key = name.lower().strip()
    for k, r in RANGES.items():
        if k in key:
            if value < r["low"] * 0.8 or value > r["high"] * 1.25:
                return "CRITICAL"
            if value < r["low"] or value > r["high"]:
                return "ABNORMAL"
            return "NORMAL"
    return "UNKNOWN"
"""Fictional Harborline RF line catalog.

Names, tool models, and spec windows are synthetic. They are not
Akoustis, SpaceX, or Starlink process parameters.
"""

from __future__ import annotations

STEPS: list[dict[str, str]] = [
    {"id": "SUBSTRATE_START", "label": "Incoming", "area": "MATERIAL"},
    {"id": "BOTTOM_ELECTRODE", "label": "Bottom electrode", "area": "ELECTRODE"},
    {"id": "PIEZO_DEPOSITION", "label": "Piezo deposition", "area": "PIEZO"},
    {"id": "TOP_ELECTRODE", "label": "Top electrode", "area": "ELECTRODE"},
    {"id": "LITHOGRAPHY", "label": "Lithography", "area": "PATTERN"},
    {"id": "ETCH", "label": "Etch", "area": "ETCH"},
    {"id": "FREQ_TRIM", "label": "Frequency trim", "area": "TRIM"},
    {"id": "RF_PROBE", "label": "RF probe", "area": "PROBE"},
    {"id": "DICE", "label": "Dice", "area": "SINGULATION"},
    {"id": "FINAL_TEST", "label": "Final test", "area": "FINAL"},
]

STEP_IDS = [step["id"] for step in STEPS]
STEP_LABELS = {step["id"]: step["label"] for step in STEPS}
FINAL_STEP = "FINAL_TEST"

TOOLS: list[dict[str, str]] = [
    {"id": "STK-01", "name": "Incoming stocker", "area": "MATERIAL", "model": "Harbor ST-100"},
    {"id": "SPT-01", "name": "Bottom electrode sputter", "area": "ELECTRODE", "model": "Helios SPD-200"},
    {"id": "SPT-02", "name": "Top electrode sputter", "area": "ELECTRODE", "model": "Helios SPD-200"},
    {"id": "DEP-01", "name": "Piezo deposition", "area": "PIEZO", "model": "Alder PVD-4"},
    {"id": "LTH-01", "name": "Stepper A", "area": "PATTERN", "model": "Quarry 193"},
    {"id": "LTH-02", "name": "Stepper B", "area": "PATTERN", "model": "Quarry 193"},
    {"id": "ETH-01", "name": "Piezo etch", "area": "ETCH", "model": "Nimbus ICP"},
    {"id": "TRM-01", "name": "Frequency trim", "area": "TRIM", "model": "Keel Trim-8"},
    {"id": "PRB-01", "name": "RF probe A", "area": "PROBE", "model": "Harbor RF-Probe"},
    {"id": "PRB-02", "name": "RF probe B", "area": "PROBE", "model": "Harbor RF-Probe"},
    {"id": "DIC-01", "name": "Dicing saw", "area": "SINGULATION", "model": "Slate DS-25"},
    {"id": "PKG-01", "name": "Final test handler", "area": "FINAL", "model": "Pier FT-9"},
]

TOOL_BY_ID = {tool["id"]: tool for tool in TOOLS}

AREAS = [
    {"id": "MATERIAL", "label": "Material"},
    {"id": "ELECTRODE", "label": "Electrode"},
    {"id": "PIEZO", "label": "Piezo"},
    {"id": "PATTERN", "label": "Pattern"},
    {"id": "ETCH", "label": "Etch"},
    {"id": "TRIM", "label": "Trim"},
    {"id": "PROBE", "label": "Probe"},
    {"id": "SINGULATION", "label": "Singulation"},
    {"id": "FINAL", "label": "Final"},
]
AREA_LABELS = {area["id"]: area["label"] for area in AREAS}

RECIPES: list[dict[str, object]] = [
    {
        "id": "XB-C-2G4",
        "name": "2.4 GHz class filter",
        "family": "Connectivity",
        "target_freq_mhz": 2442.0,
        "die_per_wafer": 2500,
    },
    {
        "id": "XB-N77",
        "name": "n77-class filter",
        "family": "Cellular",
        "target_freq_mhz": 3700.0,
        "die_per_wafer": 2500,
    },
    {
        "id": "XB-S-KU",
        "name": "Ku-class filter",
        "family": "Satellite",
        "target_freq_mhz": 12000.0,
        "die_per_wafer": 1800,
    },
]
RECIPE_BY_ID = {str(recipe["id"]): recipe for recipe in RECIPES}

# Synthetic control windows for the demo line. Not product specifications.
METRICS: list[dict[str, object]] = [
    {
        "id": "piezo_thickness_nm",
        "label": "Piezo thickness",
        "unit": "nm",
        "description": "Deposited piezoelectric film thickness",
    },
    {
        "id": "resonance_mhz",
        "label": "Resonance",
        "unit": "MHz",
        "description": "Series resonance after trim / at probe",
    },
    {
        "id": "insertion_loss_db",
        "label": "Insertion loss",
        "unit": "dB",
        "description": "Passband insertion loss magnitude",
    },
]
METRIC_BY_ID = {str(metric["id"]): metric for metric in METRICS}
METRIC_UNITS = {str(metric["id"]): str(metric["unit"]) for metric in METRICS}

TOOL_STATES = ("IDLE", "SETUP", "EXECUTING", "PAUSE", "ALARM", "DOWN")
ALARM_SEVERITIES = ("warning", "alarm", "critical")
LOT_STATUSES = ("QUEUED", "WIP", "HOLD", "COMPLETE", "SCRAPPED")

# Collection-event inspired identifiers. The demo speaks JSON, not HSMS.
CEID_TOOL_STATE = 1001
CEID_ALARM_SET = 2001
CEID_ALARM_CLEAR = 2002
CEID_TRACK_IN = 3001
CEID_TRACK_OUT = 3002
CEID_SCRAP = 3003
CEID_HOLD = 3004


def recipe_specs(recipe_id: str) -> list[dict[str, object]]:
    recipe = RECIPE_BY_ID[recipe_id]
    target = float(recipe["target_freq_mhz"])
    insertion = {
        "XB-C-2G4": (0.55, 2.10, 1.05),
        "XB-N77": (0.60, 2.30, 1.15),
        "XB-S-KU": (0.70, 2.80, 1.40),
    }[recipe_id]
    return [
        {
            "metric": "piezo_thickness_nm",
            "unit": "nm",
            "lsl": 970.0,
            "usl": 1030.0,
            "target": 1000.0,
        },
        {
            "metric": "resonance_mhz",
            "unit": "MHz",
            "lsl": round(target * 0.99, 3),
            "usl": round(target * 1.01, 3),
            "target": target,
        },
        {
            "metric": "insertion_loss_db",
            "unit": "dB",
            "lsl": insertion[0],
            "usl": insertion[1],
            "target": insertion[2],
        },
    ]


def step_tools(step: str) -> list[str]:
    """Tools that can run a route step. Single-tool steps are bottlenecks."""
    return {
        "SUBSTRATE_START": ["STK-01"],
        "BOTTOM_ELECTRODE": ["SPT-01"],
        "PIEZO_DEPOSITION": ["DEP-01"],
        "TOP_ELECTRODE": ["SPT-02"],
        "LITHOGRAPHY": ["LTH-01", "LTH-02"],
        "ETCH": ["ETH-01"],
        "FREQ_TRIM": ["TRM-01"],
        "RF_PROBE": ["PRB-01", "PRB-02"],
        "DICE": ["DIC-01"],
        "FINAL_TEST": ["PKG-01"],
    }[step]

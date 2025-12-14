QRS_GRAPH = {
    "QRS": {"question": "Is a QRS complex present?", "choices": ["Yes", "No (Asystole)"]},
    "Pacing": {"question": "Is pacing present?", "choices": ["Yes", "No"]},
    "Axis": {
        "question": "What is the axis of the QRS complex?",
        "choices": [
            "normal",
            "Right/LPFB",
            "Left/LAFB",
            "NW",
        ],
    },
    "Lead reversal": {
        "question": "Is there a lead reversal present?",
        "choices": [
            "No",
            "LA/RA",
            "LA/LL",
            "RA/RL",
            "Other",
        ],
    },
    "Rate": {
        "question": "What is the rate of the QRS complex?",
        "choices": [
            "Bradycardia",
            "Tachycardia",
            "Normal",
        ],
    },
    "Amplitude": {
        "question": "What is the amplitude of the QRS complex?",
        "choices": [
            "Normal",
            "LVH/RVH",
            "Low",
        ],
    },
    "Preexcitation": {"question": "Is there a preexcitation present?", "choices": ["Yes", "No"]},
    "AP": {
        "question": "What is the accessory pathway (AP)?",
        "choices": [
            "Normal",
            "Right/LPFB",
            "Left/LAFG",
            "NW",
        ],
    },
    "Duration": {
        "question": "What is the duration of the QRS complex in milliseconds?",
        "choices": [
            "<110",
            ">120",
            "110-120",
        ],
    },
    ">120": {
        "question": "If the duration is >120, please specify:",
        "choices": [
            "IVCD",
            "RBBB",
            "LBBB",
        ],
    },
    "110-120": {
        "question": "If the duration is 110-120, please specify:",
        "choices": [
            "incomplete LBBB",
            "incomplete RBBB",
            "Other",
        ],
    },
    "<110": {
        "question": "If the duration is <110, please specify:",
        "choices": [
            "rSR complex in V1",
            "Normal V1",
        ],
    },
}

T_GRAPH = {
    "T": {
        "question": "What is the morphology of the T wave?",
        "choices": [
            "Normal",
            "Peaked",
            "Inverted",
            "Nonspecific",
        ],
    },
}

LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]

NOISE_ARTIFACTS_GRAPH = {
    "Noise artifacts": {
        "question": "Select any issues that are present in the ECG signal.",
        "choices": [
            "Missing lead",
            "Noise",
            "Artifacts",
            "Other",
            "None",
        ],
        "multilabel": True,
    },
    "Missing lead leads": {
        "question": "Which leads have missing data?",
        "choices": LEADS,
        "multilabel": True,
    },
    "Noise leads": {
        "question": "Which leads are affected by noise?",
        "choices": LEADS,
        "multilabel": True,
    },
    "Artifacts leads": {
        "question": "Which leads are affected by artifacts?",
        "choices": LEADS,
        "multilabel": True,
    },
    "Other leads": {
        "question": "Which leads are affected by other issues?",
        "choices": LEADS,
        "multilabel": True,
    },
}

NOISE_LEAD_QUESTIONS = ["Missing lead leads", "Noise leads", "Artifacts leads", "Other leads"]

NOISE_TO_LEAD_QUESTION = {
    "Missing lead": "Missing lead leads",
    "Noise": "Noise leads",
    "Artifacts": "Artifacts leads",
    "Other": "Other leads",
}

ALL_QUESTIONS_GRAPH = {**QRS_GRAPH, **NOISE_ARTIFACTS_GRAPH, **T_GRAPH}

QRS_QUESTION_ORDER = ["QRS", "Pacing", "Axis", "Lead reversal", "Rate", "Amplitude", "Preexcitation", "AP", "Duration"]
NOISE_ARTIFACTS_QUESTION_ORDER = ["Noise artifacts"] + NOISE_LEAD_QUESTIONS
T_QUESTION_ORDER = ["T"]
ALL_QUESTION_ORDER = NOISE_ARTIFACTS_QUESTION_ORDER + QRS_QUESTION_ORDER + T_QUESTION_ORDER

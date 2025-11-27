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
            "LA/RA",
            "LA/LL",
            "RA/RL",
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
        "question": "What is the AP?",
        "choices": [
            "Normal",
            "Right/LPFB",
            "Left/LAFG",
            "NW",
        ],
    },
    "Duration": {
        "question": "What is the duration of the QRS complex?",
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
            "RBB",
            "LBBB",
        ],
    },
    "110-120": {
        "question": "If the duration is 110-120, please specify:",
        "choices": [
            "iLBBB",
            "iRBB",
            "Other",
        ],
    },
    "<110": {
        "question": "If the duration is <110, please specify:",
        "choices": [
            "rSR'",
            "None",
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

NOISE_ARTIFACTS_GRAPH = {
    "Noise artifacts": {
        "question": "What kind of noise artifacts are present?",
        "choices": [
            "Missing",
            "LVAD",
            "Noise",
        ],
    },
}

ALL_QUESTIONS_GRAPH = {**QRS_GRAPH, **NOISE_ARTIFACTS_GRAPH, **T_GRAPH}

QRS_QUESTION_ORDER = ["QRS", "Pacing", "Axis", "Lead reversal", "Rate", "Amplitude", "Preexcitation", "AP", "Duration"]
NOISE_ARTIFACTS_QUESTION_ORDER = ["Noise artifacts"]
T_QUESTION_ORDER = ["T"]
ALL_QUESTION_ORDER = QRS_QUESTION_ORDER + NOISE_ARTIFACTS_QUESTION_ORDER + T_QUESTION_ORDER

SECTIONS = [
    ("QRS", QRS_GRAPH),
    ("Noise Artifacts", NOISE_ARTIFACTS_GRAPH),
    ("T", T_GRAPH),
]

if __name__ == "__main__":
    print(SECTIONS)

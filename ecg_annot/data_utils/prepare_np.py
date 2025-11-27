import numpy as np
from ecg_annot.data_utils.prepare_xml import PTB_ORDER


def load_ecg_signals_only(npy_path: str) -> np.ndarray:
    arr = np.load(npy_path)
    if arr.ndim != 2:
        raise ValueError(f"Expected 2D array, got {arr.ndim}D array")
    if arr.shape[0] == len(PTB_ORDER):
        return arr.astype(np.float32)
    elif arr.shape[1] == len(PTB_ORDER):
        return arr.T.astype(np.float32)
    else:
        raise ValueError(f"Expected shape ({len(PTB_ORDER)}, T) or (T, {len(PTB_ORDER)}), got {arr.shape}")

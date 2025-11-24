import xml.etree.ElementTree as ET
from typing import Dict
import numpy as np
import base64

PTB_ORDER = ["I", "II", "III", "aVL", "aVR", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]


def _prefer_waveform(lead_dict: Dict[str, Dict[str, np.ndarray]], lead_id: str) -> np.ndarray | None:
    if lead_id not in lead_dict:
        return None
    if "Rhythm" in lead_dict[lead_id]:
        return lead_dict[lead_id]["Rhythm"]
    for _, arr in lead_dict[lead_id].items():
        return arr
    return None


def _canon_lead_id(s: str | None) -> str | None:
    if not s:
        return None
    t = s.strip().replace(" ", "").replace("-", "")
    u = t.upper()
    if u in {"AVR", "AVL", "AVF"}:
        return {"AVR": "aVR", "AVL": "aVL", "AVF": "aVF"}[u]
    if u in {"I", "II", "III"}:
        return u
    if u in {"1", "2", "3"}:
        return {"1": "I", "2": "II", "3": "III"}[u]
    if u.startswith("V") and u[1:].isdigit():
        return "V" + str(int(u[1:]))
    return t


def _derive_limb_leads(leads: Dict[str, np.ndarray]) -> None:
    I = leads.get("I")
    II = leads.get("II")
    III = leads.get("III")
    if I is not None and II is not None and III is None:
        leads["III"] = II - I
        III = leads["III"]
    if I is not None and II is not None and III is not None:
        leads.setdefault("aVR", -0.5 * (I + II))
        leads.setdefault("aVL", 0.5 * (I - III))
        leads.setdefault("aVF", 0.5 * (II + III))


def _decode_waveform(waveform_b64: str, units_per_bit: float) -> np.ndarray:
    raw = np.frombuffer(base64.b64decode(waveform_b64), dtype=np.int16).astype(np.float32)
    return raw * float(units_per_bit)


def _stack_ptb_12(by_lead: Dict[str, Dict[str, np.ndarray]]) -> np.ndarray:
    chosen: Dict[str, np.ndarray] = {}
    for lead_id in list(by_lead.keys()):
        sel = _prefer_waveform(by_lead, lead_id)
        if sel is not None:
            chosen[lead_id] = sel

    _derive_limb_leads(chosen)

    available = {k: v for k, v in chosen.items() if k in set(PTB_ORDER)}
    missing = [l for l in PTB_ORDER if l not in available]
    if missing:
        raise ValueError(f"Missing required leads after derivation: {missing}")

    min_len = min(len(v) for v in available.values())
    trimmed = {k: v[:min_len] for k, v in available.items()}
    return np.stack([trimmed[l] for l in PTB_ORDER], axis=0)


def _extract_signals_type2(root: ET.Element) -> np.ndarray:
    by_lead: Dict[str, Dict[str, np.ndarray]] = {}
    for wf in root.findall(".//Waveform"):
        wf_type = wf.findtext("WaveformType") or ""
        for ld in wf.findall("LeadData"):
            lead_id = _canon_lead_id(ld.findtext("LeadID"))
            if not lead_id:
                continue
            upb_txt = ld.findtext("LeadAmplitudeUnitsPerBit")
            try:
                units_per_bit = float(upb_txt) if upb_txt is not None else 1.0
            except ValueError:
                units_per_bit = 1.0
            wf_b64 = ld.findtext("WaveFormData") or ""
            arr = _decode_waveform(wf_b64, units_per_bit)
            by_lead.setdefault(lead_id, {})[wf_type] = arr

    return _stack_ptb_12(by_lead)


def _extract_signals_type1(root: ET.Element) -> np.ndarray:
    by_lead: Dict[str, Dict[str, np.ndarray]] = {}
    for wf in root.findall(".//Waveform"):
        wf_type = wf.findtext("WaveformType") or ""
        for ld in wf.findall("LeadData"):
            lead_id = ld.findtext("LeadID")
            if not lead_id:
                continue
            units_per_bit = float(ld.findtext("LeadAmplitudeUnitsPerBit"))
            wf_b64 = ld.findtext("WaveFormData") or ""
            arr = _decode_waveform(wf_b64, units_per_bit)
            by_lead.setdefault(lead_id, {})[wf_type] = arr

    return _stack_ptb_12(by_lead)


def load_ecg_signals_only(xml_path: str) -> np.ndarray:
    root = ET.parse(xml_path).getroot()

    first_err: Exception | None = None
    try:
        return _extract_signals_type2(root)
    except Exception as e:
        first_err = e

    try:
        return _extract_signals_type1(root)
    except Exception as e2:
        raise RuntimeError(f"Failed to decode ECG from {xml_path} with both XML types. Type2 error: {first_err}; Type1 error: {e2}")

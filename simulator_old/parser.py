# ===============================
# file: parser.py
# ===============================
from typing import Iterator, Dict, Tuple, List
import re, math

STEP_MM = 5.0                          # segment length for interpolation
_EXPR   = re.compile(r'([A-Z])([-+]?\d*\.?\d+)')

def _parse(line: str) -> Dict[str, float]:
    return {m[0]: float(m[1]) for m in _EXPR.findall(line.upper())}

def _interp(p0: Tuple[float, float, float],
            p1: Tuple[float, float, float]) -> List[Tuple[float, float, float]]:
    dx, dy, dz = (p1[i] - p0[i] for i in range(3))
    length = math.hypot(math.hypot(dx, dy), dz)
    if length == 0:
        return []
    n = max(1, int(length / STEP_MM))
    return [(p0[0] + dx * i / n,
             p0[1] + dy * i / n,
             p0[2] + dz * i / n) for i in range(1, n + 1)]

def pose_stream(path: str) -> Iterator[Dict[str, float]]:
    """
    Yields dicts  {"X":..,"Y":..,"Z":..,"C":..,"G":0|1}
    Handles modal G-codes: a G word is sticky until another appears.
    Only G0 and G1 moves are emitted.
    """
    modal = {"X": 0.0, "Y": 0.0, "Z": 0.0, "C": 0.0, "G": 1}   # default to G1
    with open(path) as fh:
        for raw in fh:
            raw = raw.partition(";")[0].strip()
            if not raw:
                continue
            words = _parse(raw)

            start = (modal["X"], modal["Y"], modal["Z"])

            # update modal state -----------------------------
            if "G" in words:
                modal["G"] = int(words["G"])
            for k in "XYZC":
                if k in words:
                    modal[k] = words[k]

            if modal["G"] not in (0, 1):
                continue                                    # ignore G2/3 for now

            end = (modal["X"], modal["Y"], modal["Z"])
            for x, y, z in _interp(start, end):
                yield {"X": x, "Y": y, "Z": z,
                       "C": modal["C"], "G": modal["G"]}

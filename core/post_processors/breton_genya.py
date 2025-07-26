# posts/breton_genya.py
from datetime import datetime

class BretonGenyaPost:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lines = []

    # ------------- helpers -------------------------
    def add(self, *chunks):
        self.lines.append(" ".join(str(c) for c in chunks if c != ""))

    # ------------- entry points --------------------
    def start_job(self, jobname, src_file):
        now = datetime.now().strftime("%d/%m/%Y - %H:%M")
        self.add(f";GENYA 600")
        self.add(f";Date and Time: {now}")
        self.add(f';File Name: {src_file}')
        self.add(f';Approximate Machining Time : 0.0 min.')
        self.add(f'MSG("{jobname}")')
        self.add("BRETON_INIT(0)")
        self.add("G518", "BRETON_WAREA(\"MILL\")", "")

    def start_tool(self, tool_num, comment, offset):
        self.add("BRETON_PRE_TOOL")
        self.add(f"T{tool_num} ;{comment}")
        self.add("BRETON_CHGTOOL")
        self.add(f"D{offset}")
        self.add("BRETON_POST_TOOL(5,0)")

    def set_orientation(self, A=0,B=0,C=0):
        self.add(f"BRETON_ORIENTATION({A},{B},{C},,,,0,0)")

    def set_work_plane(self, x,y,z,a,b,c):
        self.add(f"BRETON_SETWPLANE({x},{y},{z},{a},{b},{c})")

    def spindle_on(self, rpm):
        self.add("MS1", f"M4S{rpm}", "M07")

    def rapid(self, x,y,z=None):
        self.add("G0", f"X{x:.4f}", f"Y{y:.4f}", "" if z is None else f"Z{z:.4f}")

    def feed(self, x,y,z,f):
        self.add("G1", f"X{x:.4f}", f"Y{y:.4f}", f"Z{z:.4f}", f"F{f}")

    def end_job(self):
        self.add("M05", "M09", "BRETON_TCP_OFF", 'BRETON_WAREA("HOME")', "M30")

    def get_text(self):
        return "\n".join(self.lines) + "\n"

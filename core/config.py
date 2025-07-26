# config.py
import json
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "config.json"

_defaults = {
    "window": { "width": 1600, "height": 1000 },
    "toolbar": { "icon_size": 50, "gap": 20 },
    "paths": { "last_opened_dxf": "" },
    # new sections:
    "machine_settings": {
        "table_orientation": "front",
        "table_length": 3500.0,
        "table_width": 2000.0,
        "max_feed_rate": 5000.0,
        "rapid_rate":      10000.0,
        "controller":      "Osai"
    },
    "tool_settings": {
        "Blade Diameter": 400,
        "Blade Width":   3.5
    },
    "toolpath_settings": {
        "start": 1000.0,
        "end": 500.0,
        "roughing_stepover": 0.5,
        "smoothing_resolution": 0.2,
        "feed_rate":          1000.0
    }
}

if not CONFIG_FILE.exists():
    CONFIG_FILE.write_text(json.dumps(_defaults, indent=4))
    config = _defaults.copy()
else:
    config = json.loads(CONFIG_FILE.read_text())

def save_config():
    CONFIG_FILE.write_text(json.dumps(config, indent=4))

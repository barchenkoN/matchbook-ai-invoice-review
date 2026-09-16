import re

import yaml

from app.db import ROOT


def test_documented_colors_match_runtime():
    text = (ROOT / "DESIGN.md").read_text()
    colors = yaml.safe_load(text.split("---")[1])["colors"]
    css = (ROOT / "frontend/src/styles.css").read_text()
    for key, value in colors.items():
        assert re.search(r"--" + re.escape(key) + r"\s*:\s*" + re.escape(value), css, re.I)

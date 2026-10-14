"""Clean ingredient text without changing quantities or preparation notes."""
import re


_PRICE = r"[$£€]\s*\d+(?:[.,]\d+)*"


def strip_ingredient_prices(line):
    """Remove source prices and footnote markers, preserving useful notes."""
    line = re.sub(r"[*†‡]+", "", line)
    line = re.sub(r"^\s*[•▪]\s*", "", line)
    line = re.sub(r"\(\s*" + _PRICE + r"\s*\)", "", line)
    line = re.sub(_PRICE, "", line)
    line = re.sub(r"\(\s*\)|\[\s*\]", "", line)
    # Price removal can leave a trailing separator or whitespace before punctuation.
    line = re.sub(r"\s+([,;:)\]])", r"\1", line)
    line = re.sub(r"\s+[-–—|:,;]\s*$", "", line)
    return re.sub(r"\s+", " ", line).strip()

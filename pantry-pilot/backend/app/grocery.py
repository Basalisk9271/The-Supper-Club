import re
from collections import defaultdict
from fractions import Fraction

UNICODE_FRACTIONS = {
    "½": 0.5, "⅓": 1/3, "⅔": 2/3, "¼": 0.25, "¾": 0.75,
    "⅕": 0.2, "⅖": 0.4, "⅗": 0.6, "⅘": 0.8, "⅙": 1/6,
    "⅚": 5/6, "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875,
}
UNITS = {
    "tsp", "tbsp", "cup", "cups", "oz", "ounce", "ounces", "lb", "lbs", "pound", "pounds",
    "g", "kg", "ml", "l", "clove", "cloves", "can", "cans", "package", "packages", "pinch",
}


def _number(token):
    token = token.strip()
    if not token:
        return None
    if token in UNICODE_FRACTIONS:
        return UNICODE_FRACTIONS[token]
    try:
        if "/" in token:
            return float(Fraction(token))
        return float(token)
    except Exception:
        # Handles 1½
        m = re.match(r"^(\d+)([{}])$".format("".join(UNICODE_FRACTIONS)), token)
        if m:
            return float(m.group(1)) + UNICODE_FRACTIONS[m.group(2)]
        return None


def parse_ingredient(line):
    clean = re.sub(r"\([^)]*\$[^)]*\)", "", line).strip()
    clean = re.sub(r"\s+", " ", clean)
    parts = clean.split()
    qty = None
    used = 0
    if parts:
        q1 = _number(parts[0])
        if q1 is not None:
            qty = q1
            used = 1
            if len(parts) > 1:
                q2 = _number(parts[1])
                if q2 is not None and q2 < 1:
                    qty += q2
                    used = 2
    unit = None
    if len(parts) > used and parts[used].lower().rstrip(".") in UNITS:
        unit = parts[used].lower().rstrip(".")
        used += 1
    name = " ".join(parts[used:]).strip(" ,") or clean
    # Remove preparation notes for grouping, but keep original in output notes.
    key = re.split(r",|\(|\b(?:divided|chopped|diced|minced|sliced|optional|to taste)\b", name, maxsplit=1, flags=re.I)[0]
    key = re.sub(r"\s+", " ", key).strip().lower()
    return {"quantity": qty, "unit": unit, "name": name, "key": key, "original": line}


def build_grocery_list(recipes, selections):
    grouped = defaultdict(lambda: {"quantity": 0.0, "unit": None, "name": None, "sources": [], "unmerged": []})
    for recipe in recipes:
        sel = selections.get(str(recipe["id"]), {})
        target_servings = float(sel.get("servings") or recipe.get("servings") or 1)
        base_servings = float(recipe.get("servings") or target_servings or 1)
        multiplier = target_servings / base_servings if base_servings else 1
        for line in recipe.get("ingredients", []):
            parsed = parse_ingredient(line)
            group_key = f"{parsed['key']}|{parsed['unit'] or ''}"
            item = grouped[group_key]
            item["name"] = parsed["name"]
            item["unit"] = parsed["unit"]
            item["sources"].append(recipe["title"])
            if parsed["quantity"] is None:
                item["unmerged"].append(parsed["original"])
            else:
                item["quantity"] += parsed["quantity"] * multiplier

    out = []
    for item in grouped.values():
        qty = round(item["quantity"], 2) if item["quantity"] else None
        display_qty = None
        if qty is not None:
            display_qty = str(int(qty)) if float(qty).is_integer() else f"{qty:g}"
        out.append({
            "name": item["name"],
            "quantity": qty,
            "quantity_display": display_qty,
            "unit": item["unit"],
            "sources": sorted(set(item["sources"])),
            "notes": item["unmerged"],
            "checked": False,
        })
    return sorted(out, key=lambda x: x["name"].lower())

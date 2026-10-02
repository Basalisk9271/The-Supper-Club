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


# First matching rule wins: specific pantry products precede their fresh names
# (for example, chicken broth is Pantry, rather than Meat & Seafood).
GROCERY_CATEGORIES = (
    "Vegetables", "Fruit", "Dairy & Eggs", "Meat & Seafood",
    "Bakery & Grains", "Pantry", "Herbs & Spices", "Frozen", "Other",
)
CATEGORY_RULES = (
    ("Frozen", r"frozen|ice cream"),
    ("Pantry", r"broth|stock|bouillon|canned|cans?|tomato (?:paste|sauce)|coconut (?:milk|cream)|(?:almond|oat|soy) milk|(?:peanut|almond|cashew|sunflower) butter|apple ?sauce|juice|oil|vinegar|sauce|paste|ketchup|mustard|mayonnaise|mayo|dressing|salsa|syrup|honey|sugar|flour|baking (?:powder|soda)|cornstarch|cocoa|chocolate|vanilla|yeast|beans?|lentils?|chickpeas?|chick peas|peas|nuts?|walnuts?|almonds?|peanuts?|pecans?|cashews?|seeds?|raisins?|tofu|tempeh"),
    ("Herbs & Spices", r"(?:garlic|onion|chili|chilli|curry) powder|(?:black|white|cayenne|ground|crushed red) pepper|pepper flakes|peppercorns?|salt|paprika|cumin|cinnamon|nutmeg|turmeric|seasoning|dried (?:basil|oregano|thyme|rosemary|parsley|dill)|oregano|bay leaves|cloves|allspice|cardamom|coriander"),
    ("Dairy & Eggs", r"milk|cream|butter|cheese|cheddar|parmesan|mozzarella|feta|ricotta|yogurt|yoghurt|eggs?|buttermilk|ghee|half.and.half"),
    ("Meat & Seafood", r"chicken|beef|pork|turkey|lamb|veal|duck|bacon|sausage|ham|steak|ground meat|salmon|tuna|shrimp|prawns?|fish|cod|tilapia|crab|lobster|scallops?|mussels?|clams?|anchovies|sardines"),
    ("Bakery & Grains", r"bread|breadcrumbs|panko|tortillas?|rolls?|buns?|bagels?|pita|rice|pasta|noodles?|spaghetti|macaroni|penne|orzo|fettuccine|linguine|lasagna|couscous|quinoa|oats?|oatmeal|barley|farro|bulgur"),
    ("Vegetables", r"onions?|shallots?|scallions?|garlic|tomato(?:es)?|potato(?:es)?|carrots?|celery|broccoli|cauliflower|spinach|kale|lettuce|cabbage|peppers?|zucchini|squash|cucumbers?|mushrooms?|asparagus|eggplants?|aubergines?|corn|green beans|green peas|snap peas|snow peas|beets?|radishes|leeks?|brussels sprouts|arugula|jalapeños?|jalapenos?|chiles?|chilies|ginger|cilantro|parsley|basil|thyme|rosemary|dill|mint"),
    ("Fruit", r"apples?|bananas?|oranges?|lemons?|limes?|avocados?|strawberr(?:y|ies)|blueberr(?:y|ies)|raspberr(?:y|ies)|berr(?:y|ies)|grapes?|pineapples?|mango(?:es)?|peach(?:es)?|pears?|melons?|watermelons?|cherries|coconut"),
)
CATEGORY_PATTERNS = [(category, re.compile(r"\b(?:" + pattern + r")\b", re.I))
                     for category, pattern in CATEGORY_RULES]


def ingredient_category(name):
    # Ignore preparation notes, which can mention unrelated ingredients.
    name = re.split(r",|\(", name, maxsplit=1)[0]
    # Fresh green beans and peas belong with produce, unlike dried legumes.
    if re.search(r"\b(?:green beans|green peas|snap peas|snow peas)\b", name, re.I) and not re.search(r"\b(?:frozen|canned|can)\b", name, re.I):
        return "Vegetables"
    for category, pattern in CATEGORY_PATTERNS:
        if pattern.search(name):
            return category
    return "Other"


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
            "category": ingredient_category(item["name"]),
            "quantity": qty,
            "quantity_display": display_qty,
            "unit": item["unit"],
            "sources": sorted(set(item["sources"])),
            "notes": item["unmerged"],
            "checked": False,
        })
    return sorted(out, key=lambda x: (GROCERY_CATEGORIES.index(x["category"]), x["name"].lower()))

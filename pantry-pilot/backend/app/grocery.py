from .ingredients import strip_ingredient_prices

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
    ("Pantry", r"broth|stock|bouillon|canned|cans?|tomato (?:paste|sauce)|coconut (?:milk|cream)|(?:almond|oat|soy) milk|(?:peanut|almond|cashew|sunflower) butter|apple ?sauce|juice|oil|vinegar|sauce|paste|ketchup|(?<!dry )(?<!ground )mustard(?! (?:powder|seeds?))|mayonnaise|mayo|dressing|salsa|syrup|honey|sugar|flour|baking (?:powder|soda)|cornstarch|cocoa|chocolate|vanilla|yeast|beans?|lentils?|chickpeas?|chick peas|peas|nuts?|walnuts?|almonds?|peanuts?|pecans?|cashews?|(?:chia|pumpkin|sunflower|flax|hemp) seeds?|raisins?|tofu|tempeh"),
    ("Herbs & Spices", r"(?:garlic|onion|chili|chilli|curry) powder|(?:black|white|cayenne|ground|cracked|crushed red) pepper|pepper flakes|peppercorns?|salt|paprika|cumin|cinnamon|nutmeg|turmeric|seasoning|dried (?:basil|oregano|thyme|rosemary|parsley|dill)|oregano|bay leaves|cloves|allspice|cardamom|coriander"),
    ("Dairy & Eggs", r"milk|cream|butter|cheese|cheddar|parmesan|mozzarella|feta|ricotta|yogurt|yoghurt|eggs?|buttermilk|ghee|half.and.half"),
    ("Meat & Seafood", r"chicken|beef|pork|turkey|lamb|veal|duck|bacon|sausage|ham|steak|ground meat|salmon|tuna|shrimp|prawns?|fish|cod|tilapia|crab|lobster|scallops?|mussels?|clams?|anchovies|sardines"),
    ("Bakery & Grains", r"bread|breadcrumbs|panko|tortillas?|rolls?|buns?|bagels?|pita|rice|pasta|noodles?|spaghetti|macaroni|penne|orzo|fettuccine|linguine|lasagna|couscous|quinoa|oats?|oatmeal|barley|farro|bulgur"),
    ("Vegetables", r"onions?|shallots?|scallions?|garlic|tomato(?:es)?|potato(?:es)?|carrots?|celery|broccoli|cauliflower|spinach|kale|lettuce|cabbage|peppers?|zucchini|squash|cucumbers?|mushrooms?|asparagus|eggplants?|aubergines?|corn|green beans|green peas|snap peas|snow peas|beets?|radishes|leeks?|brussels sprouts|arugula|jalapeños?|jalapenos?|chiles?|chilies|ginger|cilantro|parsley|basil|thyme|rosemary|dill|mint"),
    ("Fruit", r"apples?|bananas?|oranges?|lemons?|limes?|avocados?|strawberr(?:y|ies)|blueberr(?:y|ies)|raspberr(?:y|ies)|berr(?:y|ies)|grapes?|pineapples?|mango(?:es)?|peach(?:es)?|pears?|melons?|watermelons?|cherries|coconut"),
)
# Additional names and regional spellings, grouped by shopping section.
EXTRA_CATEGORY_TERMS = {
    "Frozen": r"hash browns?|tater tots?|sorbet|sherbet",
    "Pantry": (
        r"tamari|miso|tahini|harissa|gochujang|sriracha|hoisin|molasses|agave|"
        r"preserves?|jams?|jell(?:y|ies)|marmalade|olives?|capers?|pickles?|"
        r"chickpeas?|garbanzo|edamame|seitan|textured vegetable protein|"
        r"cashews?|pistachios?|hazelnuts?|macadamias?|pine nuts|"
        r"dried (?:fruit|cranberries|apricots|dates|figs)|currants|prunes|"
        r"corn ?starch|arrowroot|gelatin|agar|baking chocolate|cacao|"
        r"crackers?|pretzels?|tortilla chips|cooking spray|"
        r"(?:almond|oat|soy|soya|rice|cashew|hemp|pea)[ -]milk|"
        r"(?:almond|cashew|apple|pumpkin|sunflower)[ -]butter|"
        r"nutritional yeast|sparkling water|seltzer|club soda|wine|beer"
    ),
    "Herbs & Spices": (
        r"cayenne|chilli|chili powder|curry powder|mustard powder|dry mustard|"
        r"(?:ground|dried|powdered|granulated) (?:ginger|garlic|onion|basil|thyme|rosemary|"
        r"parsley|dill|mint|sage|chives|tarragon|marjoram|fennel)|"
        r"(?:ginger|mustard|cayenne|fennel) powder|"
        r"bay leaf|sage|marjoram|tarragon|saffron|sumac|fenugreek|anise|"
        r"caraway|celery seed|mustard seeds?|fennel seeds?|poppy seeds?|sesame seeds?|"
        r"garam masala|five[ -]spice|za[’']?atar|ras el hanout|"
        r"italian herbs|herbes de provence|old bay|adobo seasoning|cajun seasoning|creole seasoning|"
        r"red pepper flakes|chile powder|chipotle powder|smoked paprika"
    ),
    "Dairy & Eggs": (
        r"kefir|skyr|creme fraiche|crème fraîche|mascarpone|burrata|"
        r"paneer|halloumi|gruy[eè]re|gouda|brie|camembert|manchego|"
        r"provolone|monterey jack|colby|pecorino|romano|queso fresco|"
        r"egg whites?|egg yolks?|half[ -]and[ -]half"
    ),
    "Meat & Seafood": (
        r"tenderloins?|sirloin|ribeye|brisket|chuck roast|short ribs?|"
        r"spareribs?|pork chops?|drumsticks?|rotisserie chicken|cornish hens?|"
        r"bison|venison|rabbit|goose|geese|prosciutto|pancetta|chorizo|"
        r"pepperoni|salami|andouille|kielbasa|bratwurst|hot dogs?|"
        r"haddock|halibut|trout|catfish|mahi[ -]mahi|swordfish|snapper|"
        r"pollock|herring|mackerel|sole|squid|calamari|octopus|crawfish|crayfish"
    ),
    "Bakery & Grains": (
        r"rigatoni|rotini|fusilli|farfalle|ravioli|tortellini|ziti|"
        r"vermicelli|angel hair|lasagne|gnocchi|udon|soba|ramen|"
        r"polenta|grits|millet|buckwheat|amaranth|semolina|"
        r"sourdough|ciabatta|baguettes?|brioche|naan|flatbreads?|"
        r"croissants?|english muffins?|matzo|matzah|lavash|"
        r"pizza dough|puff pastry|phyllo|filo|pie crust|wonton wrappers?"
    ),
    "Vegetables": (
        r"bok choy|pak choi|chard|collard greens|mustard greens|"
        r"watercress|endive|escarole|radicchio|romaine|fennel|"
        r"artichokes?|okra|turnips?|parsnips?|rutabagas?|swede|"
        r"sweet potatoes|yams?|celeriac|jicama|daikon|bamboo shoots|"
        r"water chestnuts|bean sprouts|alfalfa sprouts|hearts of palm|"
        r"sugar snap peas|mangetout|sugar peas|haricots verts|"
        r"serrano|poblano|habanero|anaheim|chillies|chili peppers?|"
        r"tomatillos?|chives|lemongrass|galangal|fresh oregano|fresh sage|fresh tarragon"
    ),
    "Fruit": (
        r"cranberr(?:y|ies)|blackberr(?:y|ies)|kiwi(?:fruit)?|"
        r"grapefruits?|tangerines?|mandarins?|clementines?|"
        r"nectarines?|apricots?|plums?|pomegranates?|papayas?|"
        r"passion fruit|dragon fruit|lychees?|guavas?|persimmons?|"
        r"cantaloupe|honeydew|fresh dates|fresh figs"
    ),
}
CATEGORY_PATTERNS = [
    (category, re.compile(r"\b(?:" + pattern + "|" + EXTRA_CATEGORY_TERMS[category] + r")\b", re.I))
    for category, pattern in CATEGORY_RULES
]


def ingredient_category(name):
    # Commas between leading descriptors are part of the ingredient name:
    # "boneless, skinless chicken breasts" must not become just "boneless".
    name = re.sub(
        r"^(?:(?:boneless|skinless|bone-in|skin-on|fresh|raw|cooked|lean|"
        r"large|small|medium|organic)(?:\s*,\s*|\s+))+",
        lambda match: match.group().replace(",", " "), name, flags=re.I,
    )
    # Preserve a parenthesized cut description before the ingredient too.
    name = re.sub(r"^\((?:boneless|skinless|boneless[ ,]+skinless)\)\s*", "", name, flags=re.I)
    # Ignore trailing preparation notes, which can mention unrelated ingredients.
    name = re.split(r",|\(", name, maxsplit=1)[0]
    # Fresh herbs and fresh green legumes belong with produce.
    if re.search(r"\b(?:fresh (?:oregano|sage|tarragon)|green beans|green peas|snap peas|snow peas|sugar peas|mangetout|haricots verts)\b", name, re.I) and not re.search(r"\b(?:frozen|canned|can|dried)\b", name, re.I):
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


# Remove preparation wording, while preserving product-defining descriptors
# such as dried, smoked, ground (beef/spices), and unsalted.
PREPARATION_WORDS = re.compile(
    r"\b(?:(?:finely|roughly|coarsely|freshly)\s+)?"
    r"(?:chopped|diced|minced|sliced|grated|shredded|peeled|"
    r"softened|melted|divided|optional)\b|\bto taste\b", re.I,
)
INGREDIENT_ALIASES = {
    "pepper": "black pepper", "ground pepper": "black pepper",
    "cracked pepper": "black pepper", "ground black pepper": "black pepper",
    "cracked black pepper": "black pepper", "black pepper ground": "black pepper",
    "black pepper cracked": "black pepper",
    "onions": "onion", "carrots": "carrot", "potatoes": "potato",
    "tomatoes": "tomato", "lemons": "lemon", "limes": "lime",
    "garlic cloves": "garlic", "garlic clove": "garlic",
}
UNIT_ALIASES = {
    "cups": "cup", "cloves": "clove", "cans": "can",
    "packages": "package",
}


def ingredient_key(name):
    """Normalize shopping identity with conservative, extensible rules."""
    # Retain comma-separated leading descriptors (boneless, skinless chicken).
    name = re.sub(
        r"^(?:(?:boneless|skinless|bone-in|skin-on)(?:\s*,\s*|\s+))+",
        lambda match: match.group().replace(",", " "), name, flags=re.I,
    )
    name = re.split(r",|\(", name, maxsplit=1)[0].lower()
    name = PREPARATION_WORDS.sub(" ", name)
    name = re.sub(r"\bfreshly\s+(?=(?:ground|cracked)\b)", "", name)
    name = re.sub(r"\s+", " ", name).strip(" ,-")
    return INGREDIENT_ALIASES.get(name, name)


def parse_ingredient(line):
    line = strip_ingredient_prices(line)
    clean = line
    clean = re.sub(
        r"(?<=[\d" + "".join(UNICODE_FRACTIONS) + r"])(?=(?:" + "|".join(sorted(UNITS, key=len, reverse=True)) + r")\b)",
        " ", clean, flags=re.I,
    )
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
    key = ingredient_key(name)
    return {"quantity": qty, "unit": unit, "name": name, "key": key, "original": line}


POUND_UNITS = {"lb", "lbs", "pound", "pounds"}
OUNCE_UNITS = {"oz", "ounce", "ounces"}
PASTA_NAMES = re.compile(
    r"\b(?:pasta|noodles?|spaghetti|macaroni|penne|orzo|fettuccine|linguine|"
    r"lasagna|lasagne|rigatoni|rotini|fusilli|farfalle|ravioli|tortellini|"
    r"ziti|vermicelli|angel hair)\b", re.I
)


def shopping_weight(ingredient):
    """Use package-friendly weight units before merging grocery amounts."""
    unit = UNIT_ALIASES.get(ingredient["unit"], ingredient["unit"])
    quantity = ingredient["quantity"]
    if unit in OUNCE_UNITS:
        unit = "oz"
    elif unit in POUND_UNITS:
        unit = "lb"
        category = ingredient_category(ingredient["key"])
        dairy = category == "Dairy & Eggs" and not re.search(r"\beggs?\b", ingredient["key"])
        pasta = PASTA_NAMES.search(ingredient["key"]) and category not in {"Pantry", "Meat & Seafood"}
        if quantity is not None and (dairy or pasta):
            quantity *= 16
            unit = "oz"
    return {**ingredient, "quantity": quantity, "unit": unit}


def is_plain_water(name):
    """Temperature and cooking notes do not make water a shopping item."""
    return bool(re.fullmatch(
        r"(?:(?:plain|tap|hot|warm|cold|cool|boiling|lukewarm|room[ -]temperature)\s+)*water"
        r"(?:\s*(?:,|\()\s*(?:divided|as needed|for boiling|for cooking|hot|warm|cold|boiling|room temperature)\s*\)?)*"
        r"(?:\s+(?:as needed|for boiling|for cooking))?",
        name.strip(), re.I,
    ))


def build_grocery_list(recipes, selections):
    grouped = defaultdict(lambda: {"quantity": 0.0, "unit": None, "name": None, "sources": [], "unmerged": []})
    for recipe in recipes:
        sel = selections.get(str(recipe["id"]), {})
        target_servings = float(sel.get("servings") or recipe.get("servings") or 1)
        base_servings = float(recipe.get("servings") or target_servings or 1)
        multiplier = target_servings / base_servings if base_servings else 1
        for line in recipe.get("ingredients", []):
            parsed = shopping_weight(parse_ingredient(line))
            if is_plain_water(parsed["name"]):
                continue
            # Preserve water types written in notes, e.g. "water (distilled)".
            if parsed["key"] == "water":
                parsed["key"] = parsed["name"].lower()
            group_key = f"{parsed['key']}|{parsed['unit'] or ''}"
            item = grouped[group_key]
            item["name"] = parsed["key"]
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

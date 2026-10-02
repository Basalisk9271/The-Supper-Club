import json
import re
from functools import lru_cache
from html import unescape
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

UA = "PantryPilot/0.1 (personal recipe organizer; respectful on-demand fetches)"
TIMEOUT = 20.0

CATEGORY_URLS = {
    "Popular": "https://www.budgetbytes.com/category/recipes/",
    "Quick": "https://www.budgetbytes.com/category/recipes/quick/",
    "One Pot": "https://www.budgetbytes.com/category/recipes/one-pot/",
    "Chicken": "https://www.budgetbytes.com/category/recipes/chicken/",
    "Vegetarian": "https://www.budgetbytes.com/category/recipes/vegetarian/",
    "Under $10": "https://www.budgetbytes.com/category/recipes/cost-per-recipe/recipes-under-10/",
    "Under $3/serving": "https://www.budgetbytes.com/category/recipes/cost-per-serving/under-3-per-serving/",
}

EXCLUDE_PATH_PARTS = (
    "/category/", "/author/", "/tag/", "/page/", "/shop/", "/meal-plans/",
    "/about/", "/contact/", "/privacy", "/terms", "/wp-", "/login/",
)


def _client():
    return httpx.Client(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
    )


def _text(v):
    if v is None:
        return None
    if isinstance(v, dict):
        return v.get("name") or v.get("text")
    return str(v).strip()


def _duration_minutes(value):
    if not value or not isinstance(value, str):
        return None
    # ISO 8601 durations typically used in Recipe schema, e.g. PT1H20M
    m = re.match(r"P(?:\d+D)?T(?:(\d+)H)?(?:(\d+)M)?", value)
    if not m:
        return None
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def _servings(value):
    if value is None:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    m = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    return float(m.group()) if m else None


def _flatten_instructions(value):
    out = []
    if isinstance(value, str):
        return [value.strip()]
    for item in value or []:
        if isinstance(item, str):
            out.append(item.strip())
        elif isinstance(item, dict):
            if item.get("@type") == "HowToSection":
                out.extend(_flatten_instructions(item.get("itemListElement", [])))
            else:
                text = item.get("text") or item.get("name")
                if text:
                    out.append(BeautifulSoup(str(text), "html.parser").get_text(" ", strip=True))
    return [x for x in out if x]


def _find_recipe_jsonld(soup):
    candidates = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or tag.get_text())
        except Exception:
            continue
        nodes = data if isinstance(data, list) else [data]
        expanded = []
        for node in nodes:
            if isinstance(node, dict) and isinstance(node.get("@graph"), list):
                expanded.extend(node["@graph"])
            else:
                expanded.append(node)
        for node in expanded:
            if not isinstance(node, dict):
                continue
            t = node.get("@type")
            types = t if isinstance(t, list) else [t]
            if "Recipe" in types:
                candidates.append(node)
    if not candidates:
        return None
    return max(candidates, key=lambda x: len(x.get("recipeIngredient", []) or []))


def fetch_recipe(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Recipe URL must start with http:// or https://")

    with _client() as client:
        r = client.get(url)
        r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    data = _find_recipe_jsonld(soup)

    source = parsed.hostname.removeprefix("www.") if parsed.hostname else "web"
    if data:
        image = data.get("image")
        if isinstance(image, list):
            image = image[0] if image else None
        if isinstance(image, dict):
            image = image.get("url") or image.get("contentUrl")
        author = data.get("author")
        if isinstance(author, list):
            author = author[0] if author else None
        tags = data.get("recipeCategory") or []
        if isinstance(tags, str):
            tags = [x.strip() for x in tags.split(",") if x.strip()]
        result = {
            "source": source,
            "source_url": str(r.url),
            "title": _text(data.get("name")) or "Untitled recipe",
            "description": BeautifulSoup(_text(data.get("description")) or "", "html.parser").get_text(" ", strip=True),
            "image_url": image,
            "author": _text(author),
            "servings": _servings(data.get("recipeYield")),
            "prep_minutes": _duration_minutes(data.get("prepTime")),
            "cook_minutes": _duration_minutes(data.get("cookTime")),
            "total_minutes": _duration_minutes(data.get("totalTime")),
            "cost_text": None,
            "ingredients": [unescape(str(x)).strip() for x in data.get("recipeIngredient", []) if str(x).strip()],
            "instructions": _flatten_instructions(data.get("recipeInstructions", [])),
            "tags": tags,
        }
    else:
        h1 = soup.find("h1")
        result = {
            "source": source,
            "source_url": str(r.url),
            "title": h1.get_text(" ", strip=True) if h1 else (soup.title.get_text(strip=True) if soup.title else "Untitled recipe"),
            "description": "",
            "image_url": None,
            "author": None,
            "servings": None,
            "prep_minutes": None,
            "cook_minutes": None,
            "total_minutes": None,
            "cost_text": None,
            "ingredients": [],
            "instructions": [],
            "tags": [],
        }

    # Budget Bytes page-level cost text fallback.
    body_text = soup.get_text(" ", strip=True)
    cost_match = re.search(r"\$\d+(?:\.\d{2})?\s+recipe\s*/\s*\$\d+(?:\.\d{2})?\s+(?:serving|per serving)", body_text, re.I)
    if cost_match:
        result["cost_text"] = cost_match.group(0)
    return result


@lru_cache(maxsize=256)
def _is_recipe_page(url):
    """Cache successful checks so browsing does not repeatedly fetch roundups."""
    recipe = fetch_recipe(url)
    return bool(recipe.get("ingredients") and recipe.get("instructions"))


def browse_budget_bytes(category="Popular", page=1):
    base = CATEGORY_URLS.get(category, CATEGORY_URLS["Popular"])
    url = base if page <= 1 else urljoin(base, f"page/{page}/")
    with _client() as client:
        r = client.get(url)
        r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    host = urlparse(base).hostname
    results, seen = [], set()

    # Only consider post cards, never navigation, account or newsletter links.
    for card in soup.select("article.post-summary"):
        title = card.select_one(".post-summary__title")
        a = title.find_parent("a", href=True) if title else None
        if a is None and title is not None:
            a = title.find("a", href=True)
        if a is None:
            continue
        p = urlparse(urljoin(str(r.url), a["href"]))
        href = p._replace(query="", fragment="").geturl()
        if p.scheme not in ("http", "https") or p.hostname != host or href in seen:
            continue
        if any(part in p.path for part in EXCLUDE_PATH_PARTS):
            continue
        if p.path in ("/", ""):
            continue
        seen.add(href)

        # Budget Bytes gives individual recipes a cost badge. Roundups share
        # the same card markup but lack this badge. Some genuine recipes also
        # omit it, so confirm those using their structured Recipe data.
        cost = card.select_one(".cost-per")
        if not (cost and re.search(r"\$\d", cost.get_text())):
            try:
                if not _is_recipe_page(href):
                    continue
            except httpx.HTTPError:
                # A failed check must not turn an unverified page into a recipe.
                continue
        text = title.get_text(" ", strip=True)
        if not text:
            continue
        img = a.find("img")
        image = (img.get("data-src") or img.get("src")) if img else None
        if image:
            image = urljoin(str(r.url), image)
        results.append({"title": text, "url": href, "image_url": image, "source": "budgetbytes.com"})
        if len(results) >= 30:
            break
    return {"category": category, "page": page, "source_url": str(r.url), "items": results}

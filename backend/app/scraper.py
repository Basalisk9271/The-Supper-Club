import json
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from xml.etree import ElementTree
from functools import lru_cache
from html import unescape
from urllib.parse import unquote, urljoin, urlparse

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


@lru_cache(maxsize=256)
def _browse_category_page(url, day):
    with _client() as client:
        r = client.get(url)
        r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    host = "www.budgetbytes.com"
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
    next_link = soup.select_one('a.next.page-numbers, a[rel="next"]')
    if next_link is None:
        current = urlparse(str(r.url))
        match = re.search(r"/page/(\d+)/?$", current.path)
        number = int(match.group(1)) if match else 1
        category_path = current.path[:match.start() + 1] if match else current.path.rstrip("/") + "/"
        expected = current._replace(path=category_path + f"page/{number + 1}/", query="", fragment="").geturl()
        next_link = next((a for a in soup.select("a[href]") if urljoin(str(r.url), a["href"]) == expected), None)
    next_url = urljoin(str(r.url), next_link.get("href", "")) if next_link else None
    if next_url and (urlparse(next_url).hostname != host or urlparse(next_url).scheme != "https"):
        next_url = None
    return results, next_url


def browse_budget_bytes(category="Popular", page=1):
    base = CATEGORY_URLS.get(category, CATEGORY_URLS["Popular"])
    url = base
    results, seen, visited = [], set(), set()
    end = page * SEARCH_PAGE_SIZE
    while url and url not in visited and len(results) <= end:
        visited.add(url)
        items, url = _browse_category_page(url, int(time.time() // 86400))
        for item in items:
            if item["url"] not in seen:
                seen.add(item["url"])
                results.append(item)
    return {"category": category, "page": page, "source_url": base,
            "items": results[end - SEARCH_PAGE_SIZE:end], "has_more": len(results) > end}



SITEMAP_INDEX = "https://www.budgetbytes.com/sitemap_index.xml"
SITEMAP_NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
SEARCH_PAGE_SIZE = 30
_catalog_lock = Lock()
_catalog_urls = ()
_catalog_expires = 0


def _budget_bytes_catalog():
    """Refresh public post URLs once daily; do not crawl every recipe."""
    global _catalog_urls, _catalog_expires
    with _catalog_lock:
        if _catalog_urls and time.monotonic() < _catalog_expires:
            return _catalog_urls
        urls = set()
        with _client() as client:
            response = client.get(SITEMAP_INDEX)
            response.raise_for_status()
            index = ElementTree.fromstring(response.text)
            for loc in index.findall("s:sitemap/s:loc", SITEMAP_NS):
                sitemap = urlparse(loc.text or "")
                if sitemap.scheme != "https" or sitemap.hostname != "www.budgetbytes.com":
                    continue
                if not re.fullmatch(r"/post-sitemap[0-9]*\.xml", sitemap.path):
                    continue
                response = client.get(loc.text)
                response.raise_for_status()
                document = ElementTree.fromstring(response.text)
                for entry in document.findall("s:url/s:loc", SITEMAP_NS):
                    url = urlparse(entry.text or "")
                    if url.scheme == "https" and url.hostname == "www.budgetbytes.com" and url.path.strip("/"):
                        if not any(part in url.path for part in EXCLUDE_PATH_PARTS):
                            urls.add(url._replace(query="", fragment="").geturl())
        if not urls:
            raise ValueError("Budget Bytes recipe catalog is unavailable. Please try again.")
        _catalog_urls = tuple(sorted(urls))
        _catalog_expires = time.monotonic() + 86400
        return _catalog_urls


def _search_words(text):
    text = unicodedata.normalize("NFKD", unquote(text)).encode("ascii", "ignore").decode().lower()
    # Treat common singular/plural recipe names alike (pancake/pancakes).
    return {word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word
            for word in re.findall(r"[a-z0-9]+", text)}


@lru_cache(maxsize=512)
def _search_recipe_card(url, day):
    recipe = fetch_recipe(url)
    if not recipe.get("ingredients") or not recipe.get("instructions"):
        return None
    return {"title": recipe["title"], "url": recipe["source_url"],
            "image_url": recipe.get("image_url"), "source": recipe["source"]}


def search_budget_bytes(query, page=1):
    query = query.strip()
    words = _search_words(query)
    if not words:
        return {"query": query, "page": page, "items": [], "has_more": False, "unavailable_count": 0}
    matches = [url for url in _budget_bytes_catalog()
               if words <= _search_words(urlparse(url).path)]
    # Exact names first, then the most focused matches, with stable pagination.
    matches.sort(key=lambda url: (len(_search_words(urlparse(url).path)), url))
    start = (page - 1) * SEARCH_PAGE_SIZE
    unavailable = 0
    results, seen = [], set()
    end = start + SEARCH_PAGE_SIZE
    # Count verified recipes, not candidates: roundups must not leave holes.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for offset in range(0, len(matches), 4):
            futures = [pool.submit(_search_recipe_card, url, int(time.time() // 86400))
                       for url in matches[offset:offset + 4]]
            for future in futures:
                try:
                    card = future.result()
                    if card and card["url"] not in seen:
                        seen.add(card["url"])
                        results.append(card)
                except (httpx.HTTPError, ValueError, TypeError):
                    unavailable += 1
            if len(results) > end:
                break
    return {"query": query, "page": page, "items": results[start:end],
            "has_more": len(results) > end, "unavailable_count": unavailable}

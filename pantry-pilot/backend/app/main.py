import os
from typing import Dict, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl

from .db import get_recipes, init_db, list_recipes, upsert_recipe
from .grocery import build_grocery_list
from .scraper import CATEGORY_URLS, browse_budget_bytes, fetch_recipe

app = FastAPI(title="Pantry Pilot API", version="0.1.0")
origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class ImportBody(BaseModel):
    url: HttpUrl


class GrocerySelection(BaseModel):
    id: int
    servings: float | None = None


class GroceryBody(BaseModel):
    recipes: List[GrocerySelection]


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/categories")
def categories():
    return list(CATEGORY_URLS.keys())


@app.get("/api/discover")
def discover(category: str = "Popular", page: int = Query(1, ge=1, le=20)):
    try:
        return browse_budget_bytes(category, page)
    except Exception as exc:
        raise HTTPException(502, f"Could not load Budget Bytes: {exc}") from exc


@app.post("/api/import")
def import_recipe(body: ImportBody):
    url = str(body.url)
    if "budgetbytes.com" not in url:
        # Parser is deliberately generic, but this warning-free path lets us expand later.
        pass
    try:
        recipe = fetch_recipe(url)
        if not recipe.get("ingredients"):
            raise HTTPException(422, "The page loaded, but no structured recipe ingredients were found.")
        return upsert_recipe(recipe)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Could not import recipe: {exc}") from exc


@app.get("/api/recipes")
def recipes(q: str = ""):
    return list_recipes(q)


@app.post("/api/grocery-list")
def grocery_list(body: GroceryBody):
    ids = [x.id for x in body.recipes]
    recipes = get_recipes(ids)
    selections: Dict[str, dict] = {str(x.id): {"servings": x.servings} for x in body.recipes}
    return {"items": build_grocery_list(recipes, selections), "recipe_count": len(recipes)}

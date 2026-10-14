import os
from typing import Dict, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, Field

from .db import (get_recipes, init_db, list_recipes, upsert_recipe, get_recipe_by_url,
                 get_meal_plan, save_meal_plan_recipe, remove_meal_plan_recipe, remove_from_cookbook)
from .grocery import build_grocery_list
from .scraper import CATEGORY_URLS, browse_budget_bytes, fetch_recipe, search_budget_bytes

app = FastAPI(title="The Supper Club API", description="Discover recipes, save a personal Cookbook, plan meals, and build a grocery list.", version="0.1.0")
origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class ImportBody(BaseModel):
    url: HttpUrl


class GrocerySelection(BaseModel):
    id: int
    servings: float | None = Field(default=None, gt=0, allow_inf_nan=False)


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
def discover(category: str = "New & Noteworthy", page: int = Query(1, ge=1, le=200), q: str = Query("", max_length=120)):
    try:
        if q.strip():
            return search_budget_bytes(q, page)
        return browse_budget_bytes(category, page)
    except Exception as exc:
        raise HTTPException(502, f"Could not load Budget Bytes: {exc}") from exc


def resolve_recipe(body: ImportBody):
    url = str(body.url)
    cached = get_recipe_by_url(url)
    if cached:
        return cached
    try:
        recipe = fetch_recipe(url)
        if not recipe.get("ingredients"):
            raise HTTPException(422, "The page loaded, but no structured recipe ingredients were found.")
        return recipe
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


@app.post("/api/preview")
def preview_recipe(body: ImportBody):
    return resolve_recipe(body)


@app.post("/api/import")
def import_recipe(body: ImportBody):
    return upsert_recipe(resolve_recipe(body), save_to_cookbook=True)


@app.get("/api/meal-plan")
def meal_plan():
    return get_meal_plan()


@app.post("/api/meal-plan")
def add_to_meal_plan(body: ImportBody):
    recipe = upsert_recipe(resolve_recipe(body), save_to_cookbook=False)
    existing = next((r for r in get_meal_plan() if r["id"] == recipe["id"]), None)
    if not existing:
        save_meal_plan_recipe(recipe["id"], recipe.get("servings") or 1)
    return get_meal_plan()


@app.patch("/api/meal-plan/{recipe_id}")
def update_meal_plan(recipe_id: int, body: GrocerySelection):
    if body.id != recipe_id or not any(r["id"] == recipe_id for r in get_meal_plan()):
        raise HTTPException(404, "Meal plan recipe not found")
    if body.servings is None:
        raise HTTPException(422, "Servings are required")
    save_meal_plan_recipe(recipe_id, body.servings)
    return get_meal_plan()


@app.delete("/api/meal-plan/{recipe_id}")
def delete_meal_plan(recipe_id: int):
    remove_meal_plan_recipe(recipe_id)
    return get_meal_plan()


@app.delete("/api/recipes/{recipe_id}")
def delete_cookbook_recipe(recipe_id: int):
    remove_from_cookbook(recipe_id)
    return {"ok": True}

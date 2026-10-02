import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = os.getenv("PANTRY_DB", str(Path(__file__).resolve().parents[2] / "pantry.db"))


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                description TEXT,
                image_url TEXT,
                author TEXT,
                servings REAL,
                prep_minutes INTEGER,
                cook_minutes INTEGER,
                total_minutes INTEGER,
                cost_text TEXT,
                ingredients_json TEXT NOT NULL,
                instructions_json TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_recipe_title ON recipes(title);
            CREATE INDEX IF NOT EXISTS idx_recipe_source ON recipes(source);
            """
        )

        columns = {row["name"] for row in conn.execute("PRAGMA table_info(recipes)")}
        if "in_cookbook" not in columns:
            conn.execute("ALTER TABLE recipes ADD COLUMN in_cookbook INTEGER NOT NULL DEFAULT 1")
        conn.execute("CREATE TABLE IF NOT EXISTS meal_plan (recipe_id INTEGER PRIMARY KEY REFERENCES recipes(id), servings REAL NOT NULL)")


def row_to_recipe(row):
    if not row:
        return None
    item = dict(row)
    item["ingredients"] = json.loads(item.pop("ingredients_json"))
    item["instructions"] = json.loads(item.pop("instructions_json"))
    item["tags"] = json.loads(item.pop("tags_json"))
    return item


def upsert_recipe(recipe, save_to_cookbook=True):
    with db() as conn:
        conn.execute(
            """
            INSERT INTO recipes (
                source, source_url, title, description, image_url, author, servings,
                prep_minutes, cook_minutes, total_minutes, cost_text,
                ingredients_json, instructions_json, tags_json, in_cookbook
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_url) DO UPDATE SET
                title=excluded.title,
                description=excluded.description,
                image_url=excluded.image_url,
                author=excluded.author,
                servings=excluded.servings,
                prep_minutes=excluded.prep_minutes,
                cook_minutes=excluded.cook_minutes,
                total_minutes=excluded.total_minutes,
                cost_text=excluded.cost_text,
                ingredients_json=excluded.ingredients_json,
                instructions_json=excluded.instructions_json,
                tags_json=excluded.tags_json,
                in_cookbook=MAX(recipes.in_cookbook, excluded.in_cookbook)
            """,
            (
                recipe["source"], recipe["source_url"], recipe["title"],
                recipe.get("description"), recipe.get("image_url"), recipe.get("author"),
                recipe.get("servings"), recipe.get("prep_minutes"), recipe.get("cook_minutes"),
                recipe.get("total_minutes"), recipe.get("cost_text"),
                json.dumps(recipe.get("ingredients", [])),
                json.dumps(recipe.get("instructions", [])),
                json.dumps(recipe.get("tags", [])), int(save_to_cookbook),
            ),
        )
        row = conn.execute("SELECT * FROM recipes WHERE source_url=?", (recipe["source_url"],)).fetchone()
        return row_to_recipe(row)


def list_recipes(search=""):
    with db() as conn:
        if search.strip():
            q = f"%{search.strip()}%"
            rows = conn.execute(
                "SELECT * FROM recipes WHERE in_cookbook=1 AND (title LIKE ? OR description LIKE ?) ORDER BY imported_at DESC",
                (q, q),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM recipes WHERE in_cookbook=1 ORDER BY imported_at DESC").fetchall()
        return [row_to_recipe(r) for r in rows]


def get_recipes(ids):
    if not ids:
        return []
    marks = ",".join("?" for _ in ids)
    with db() as conn:
        rows = conn.execute(f"SELECT * FROM recipes WHERE id IN ({marks})", ids).fetchall()
        return [row_to_recipe(r) for r in rows]


def get_recipe_by_url(url):
    with db() as conn:
        return row_to_recipe(conn.execute("SELECT * FROM recipes WHERE source_url=?", (url,)).fetchone())


def get_meal_plan():
    with db() as conn:
        rows = conn.execute("SELECT recipes.*, meal_plan.servings AS planned_servings FROM meal_plan JOIN recipes ON recipes.id=meal_plan.recipe_id ORDER BY recipe_id").fetchall()
        return [row_to_recipe(row) for row in rows]


def save_meal_plan_recipe(recipe_id, servings):
    with db() as conn:
        conn.execute("INSERT INTO meal_plan (recipe_id, servings) VALUES (?, ?) ON CONFLICT(recipe_id) DO UPDATE SET servings=excluded.servings", (recipe_id, servings))


def remove_meal_plan_recipe(recipe_id):
    with db() as conn:
        conn.execute("DELETE FROM meal_plan WHERE recipe_id=?", (recipe_id,))


def remove_from_cookbook(recipe_id):
    with db() as conn:
        conn.execute("UPDATE recipes SET in_cookbook=0 WHERE id=?", (recipe_id,))

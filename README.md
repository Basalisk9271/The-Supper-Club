# The Supper Club

Good food. Shared plans. The Supper Club is a local-first app for discovering recipes, keeping a personal Cookbook, planning meals, and turning them into a grocery list. Its responsive dark theme uses charcoal surfaces, warm cream text, and amber accents.

## What you can do

- **Discover:** Start with New & Noteworthy, showing recipes from Budget Bytes’ [Newest Recipes section](https://www.budgetbytes.com/category/recipes/#recent) in source order, or browse Budget Bytes categories or search recipe names across its public catalog. Submit searches with **Search** or **Enter**. Searches span all categories; Cookbook search only filters your saved recipes.
- **Browse 30 recipes per page:** Pages fill with up to 30 verified recipes where available. Wide screens show up to five cards per row; phones show one. Collections and account links are excluded.
- **Preview recipes:** Open a card or paste a recipe URL to view ingredients and instructions in a modal. Close it with X or Escape. Ingredients use two columns when space allows.
- **Import from other sites:** Paste a public recipe URL. Import requires structured Recipe data with ingredients; compatibility depends on the source website. Automatic discovery currently supports Budget Bytes only.
- **Keep a Cookbook:** Save favorites for easy access. Removing a Cookbook recipe does not remove it from your Meal Plan.
- **Plan meals:** Save any recipe to the Grocery List to add it to your Meal Plan, without needing to save it in the Cookbook. Meal selections and serving amounts persist across reloads.
- **Shop from one list:** Ingredient quantities scale with servings and compatible entries combine. Items appear in food sections such as Vegetables, Dairy & Eggs, Meat & Seafood, and Pantry. Change servings or remove a meal to update the list.
- **Copy groceries:** Copy includes section headings, quantities, units, and checked states. A confirmation appears on success; a selectable list is offered if the browser blocks copying.

The logo returns to Discover. Recipe previews link to the **Original Page** for source details.

## Run with Docker

From the repository root, with Docker and Docker Compose installed:

```bash
docker compose up -d --build
```

- App: http://localhost:5173
- API documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/health

Apply updates with the same command. Rebuild only the relevant service with `docker compose up -d --build web` or `docker compose up -d --build api`.

```bash
docker compose logs -f api web
docker compose down
```

The existing `pantry_data` volume and `/data/pantry.db` filename are retained so the rebrand preserves existing data. Avoid `docker compose down -v` unless you intend to delete that volume. Keep using the same Compose project/directory when updating an existing installation; a different project name normally creates a different volume.

## Local development

Use Python 3.10+ and a current Node.js LTS release compatible with Vite. Start the backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

On Windows, activate the environment with `.venv\Scripts\activate`.

In a second terminal, start the frontend (POSIX shell):

```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

For Windows or a persistent setting, put `VITE_API_URL=http://localhost:8000` in `frontend/.env.local`, then run `npm run dev`. Open http://localhost:5173. The Docker frontend proxies `/api` requests to the API; the development server uses `VITE_API_URL` to reach it directly.

## Configuration and storage

| Setting | Purpose |
| --- | --- |
| `SUPPER_CLUB_DB` | Optional SQLite database path; takes precedence over `PANTRY_DB`. |
| `PANTRY_DB` | Backward-compatible database setting used by the existing Docker configuration. |
| `CORS_ORIGINS` | Comma-separated permitted frontend origins; defaults to `http://localhost:5173`. |
| `VITE_API_URL` | Frontend API origin. Leave empty with the Docker proxy; set for local development. Read at frontend build/start time. |

Without a database setting, the backend uses `backend/pantry.db`. Cookbook membership, imported recipes, and Meal Plan selections live in SQLite. Grocery checkmarks are browser-session state and reset when the list is rebuilt or the page reloads.

## Search and ingredient behavior

Budget Bytes discovery uses public category pages and post sitemaps, rather than its disallowed `/search/*` and `/?s...` routes. Search matches words in recipe URLs, not full article text. The catalog is cached in memory for 24 hours; category pages and verified search cards are cached by day. Matching search pages are checked for structured ingredients and instructions with at most four concurrent requests. Upstream failures can leave some results unavailable; Refresh retries the request. Use the app for personal/local use and keep request rates conservative.

Grocery sections are inferred from ingredient names, with unrecognized items under **Other**. Grouping uses ingredient names and compatible units; it does not fully interpret every preparation note, package size, or ingredient synonym.

Pasta and dairy weights in pounds convert to ounces before combining amounts (1 lb = 16 oz). Cups, tablespoons, grams, and other units remain as supplied. The app does not convert volume into weight or infer how many retail packages to buy. Quantities currently display calculated amounts rounded to two decimal places; fraction display, shopping round-up, and an extra-quantity buffer are not implemented.

## Project structure

- `frontend/`: React, Vite, Lucide icons, responsive dark-theme styles.
- `backend/app/`: FastAPI routes, SQLite storage, recipe discovery/import, grocery grouping.
- `backend/tests/`: Regression tests for discovery, search, Cookbook/Meal Plan independence, and grocery quantities.
- `docker-compose.yml`: API and Nginx frontend services with persistent SQLite storage.
- `pantry-pilot/`: Existing mirrored application directory, retained for compatibility. Use the root project for the commands above; application changes are mirrored in both copies.

## Validation

With backend dependencies installed, run from the repository root:

```bash
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
npm run build --prefix frontend
```

The app is intended for local use and has no user accounts or access controls. Recipe availability and import compatibility depend on the original websites.

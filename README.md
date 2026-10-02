# Pantry Pilot

A local-first recipe browser, recipe library, and grocery-list builder focused on Budget Bytes.

## What it does

- Browse Budget Bytes categories, or search recipe names across its public sitemap catalog.
- Submit Discover searches with Search or Enter; results span all categories and support pagination.
- Preview a recipe from a card or its public URL in a closable modal.
- Save favorites to your Cookbook independently of your Meal Plan.
- Add any recipe directly to the Grocery List; its Meal Plan membership and servings persist across reloads.
- Parse standard Recipe JSON-LD when available, with HTML fallbacks.
- Cache imported recipes in SQLite for instant local search.
- Change Meal Plan servings or remove meals to automatically update the Grocery List.
- Build a combined grocery list with lightweight ingredient normalization.
- Keeps the backend source-adapter pattern ready for additional recipe sites and meal planning.

## Architecture

- `frontend/`: React + Vite single-page UI
- `backend/`: FastAPI API + SQLite cache
- Recipe content is fetched on demand from the original source and stored locally.

## Run locally

### Option A: Docker Compose

```bash
docker compose up --build
```

Then open http://localhost:5173.

### Option B: Development mode

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend (new terminal):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Notes on Budget Bytes

This app intentionally does not call Budget Bytes' `/search/*` or `/?s...` routes. Discovery uses public category pages. Search matches recipe names in public post URLs from a sitemap catalog cached for 24 hours, then verifies matching pages contain recipe ingredients and instructions. It does not search full article text. Result pages check up to 12 candidates with at most four concurrent requests; non-recipes are excluded. Verified cards are cached for the day. Please use it for personal/local use and keep request rates conservative.

## Natural next steps

1. Weekly meal-plan calendar.
2. Pantry inventory and "already have this" exclusions.
3. Grocery-store aisle categorization.
4. Drag-and-drop meal planning.
5. Additional recipe sources.
6. Authentication and Postgres for deployment to a personal site.

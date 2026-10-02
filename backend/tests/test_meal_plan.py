import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import db, main

RECIPE = {'source': 'budgetbytes.com', 'source_url': 'https://www.budgetbytes.com/soup/',
          'title': 'Soup', 'servings': 2, 'ingredients': ['2 cups broth'], 'instructions': ['Simmer.']}


class MealPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = patch.object(db, 'DB_PATH', str(Path(self.temp.name) / 'test.db'))
        self.database.start()
        self.addCleanup(self.database.stop)
        self.fetch = patch.object(main, 'fetch_recipe', return_value=RECIPE.copy()).start()
        self.addCleanup(patch.stopall)
        self.client = TestClient(main.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def post(self, endpoint):
        result = self.client.post(endpoint, json={'url': RECIPE['source_url']})
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def test_preview_does_not_save_anything(self):
        self.assertEqual(self.post('/api/preview')['ingredients'], ['2 cups broth'])
        self.assertEqual(self.client.get('/api/recipes').json(), [])
        self.assertEqual(self.client.get('/api/meal-plan').json(), [])
        with db.db() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM recipes').fetchone()[0], 0)

    def test_plan_without_cookbook_persists_scales_and_removes(self):
        recipe = self.post('/api/meal-plan')[0]
        self.assertEqual(self.client.get('/api/recipes').json(), [])
        recipe_id = recipe['id']
        response = self.client.patch(f'/api/meal-plan/{recipe_id}', json={'id': recipe_id, 'servings': 4})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.post('/api/meal-plan')[0]['planned_servings'], 4)
        db.init_db()
        self.assertEqual(len(self.client.get('/api/meal-plan').json()), 1)
        grocery = self.client.post('/api/grocery-list', json={'recipes': [{'id': recipe_id, 'servings': 4}]}).json()
        self.assertEqual(grocery['items'][0]['quantity'], 4)
        self.assertEqual(self.client.delete(f'/api/meal-plan/{recipe_id}').json(), [])
        self.assertEqual(self.client.get('/api/recipes').json(), [])

    def test_cookbook_and_plan_are_independent(self):
        recipe_id = self.post('/api/meal-plan')[0]['id']
        saved = self.post('/api/import')
        self.assertEqual(saved['id'], recipe_id)
        self.assertEqual(len(self.client.get('/api/recipes').json()), 1)
        self.post('/api/meal-plan')
        self.assertEqual(len(self.client.get('/api/recipes').json()), 1)
        self.client.delete(f'/api/meal-plan/{recipe_id}')
        self.assertEqual(len(self.client.get('/api/recipes').json()), 1)
        self.assertEqual(self.client.get('/api/recipes?q=absent').json(), [])

    def test_cookbook_save_does_not_add_to_plan(self):
        self.post('/api/import')
        self.assertEqual(self.client.get('/api/meal-plan').json(), [])

    def test_invalid_servings_rejected(self):
        recipe_id = self.post('/api/meal-plan')[0]['id']
        for servings in [0, -1, None]:
            response = self.client.patch(f'/api/meal-plan/{recipe_id}', json={'id': recipe_id, 'servings': servings})
            self.assertEqual(response.status_code, 422)

    def test_existing_library_migrates_to_cookbook(self):
        self.post('/api/import')
        with db.db() as conn:
            conn.execute('ALTER TABLE recipes DROP COLUMN in_cookbook')
        db.init_db()
        self.assertEqual(self.client.get('/api/recipes').json()[0]['title'], 'Soup')


if __name__ == '__main__':
    unittest.main()

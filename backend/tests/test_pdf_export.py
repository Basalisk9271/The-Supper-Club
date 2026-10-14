import unittest
from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient
from pypdf import PdfReader
from app.main import app


class PdfExportTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.recipe = {'id': 7, 'title': 'Soup & greens <fresh>', 'servings': 2,
                       'ingredients': ['2 cups broth', '½ cup rice'],
                       'instructions': ['Simmer & serve.'], 'source_url': 'https://example.com/soup'}

    def test_order_scaling_checks_and_escaping(self):
        with patch('app.main.get_recipes', return_value=[self.recipe]):
            response = self.client.post('/api/meal-plan/pdf', json={
                'recipes': [{'id': 7, 'servings': 4}],
                'checked_items': [{'name': 'broth', 'unit': 'cups'}]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['content-type'], 'application/pdf')
        self.assertIn('attachment;', response.headers['content-disposition'])
        pages = PdfReader(BytesIO(response.content)).pages
        self.assertEqual(len(pages), 2)
        self.assertIn('Grocery list', pages[0].extract_text())
        self.assertIn('[x] 4 cups broth', pages[0].extract_text())
        text = pages[1].extract_text()
        self.assertIn('Soup & greens <fresh>', text)
        self.assertIn('4 cups broth', text)
        self.assertIn('1 cup rice', text)
        self.assertIn('1. Simmer & serve.', text)
        self.assertIn('https://example.com/soup', text)

    def test_invalid_selection(self):
        for recipes in ([], [{'id': 7}, {'id': 7}], [{'id': 7, 'servings': 0}]):
            self.assertEqual(self.client.post('/api/meal-plan/pdf', json={'recipes': recipes}).status_code, 422)
        with patch('app.main.get_recipes', return_value=[]):
            self.assertEqual(self.client.post('/api/meal-plan/pdf', json={'recipes': [{'id': 99}]}).status_code, 404)

    def test_long_recipe_paginates(self):
        self.recipe['instructions'] = ['Stir gently. ' * 30] * 60
        with patch('app.main.get_recipes', return_value=[self.recipe]):
            response = self.client.post('/api/meal-plan/pdf', json={'recipes': [{'id': 7}]})
        self.assertEqual(response.status_code, 200)
        pages = PdfReader(BytesIO(response.content)).pages
        self.assertGreater(len(pages), 3)
        self.assertIn('60. Stir gently.', ''.join(page.extract_text() for page in pages))

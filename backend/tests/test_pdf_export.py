import unittest
from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient
from pypdf import PdfReader
from app.main import app
from app.grocery import UNICODE_FRACTIONS, parse_ingredient
from app.pdf_export import pdf_text, pdfmetrics


class PdfExportTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.recipe = {'id': 7, 'title': 'Soup & greens <fresh>', 'servings': 2,
                       'description': 'A cozy soup & greens <fresh> favorite.',
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
        self.assertIn(self.recipe['description'], text)
        self.assertIn('4 cups broth', text)
        self.assertIn('1 cup rice', text)
        self.assertIn('1. Simmer & serve.', text)
        self.assertIn('Recipe: Soup & greens <fresh>', text)
        self.assertIn('Link: https://example.com/soup', text)
        self.assertNotIn('Original recipe:', text)
        links = [annotation.get_object() for annotation in pages[1].get('/Annots', [])]
        self.assertTrue(any(link.get('/A', {}).get('/URI') == self.recipe['source_url'] for link in links))

    def test_grocery_columns_and_recipe_page_numbers(self):
        first = {**self.recipe, 'ingredients': [f'1 cup ingredient {i}' for i in range(100)],
                 'instructions': ['Stir gently. ' * 30] * 25}
        second = {**self.recipe, 'id': 8, 'title': 'Second recipe'}
        with patch('app.main.get_recipes', return_value=[second, first]):
            response = self.client.post('/api/meal-plan/pdf', json={
                'recipes': [{'id': 7}, {'id': 8}]})
        pages = PdfReader(BytesIO(response.content)).pages
        first_recipe_page = next(i for i, page in enumerate(pages)
                                 if 'Planned servings:' in page.extract_text())
        grocery_text = ''.join(page.extract_text() for page in pages[:first_recipe_page])
        self.assertNotIn(first['title'], grocery_text)
        self.assertNotIn(second['title'], grocery_text)
        self.assertIn('Checked items are marked [x]', grocery_text)
        positions = []
        def collect(text, cm, tm, font, size):
            if 'ingredient' in text:
                positions.append(cm[4] + tm[4])
        pages[0].extract_text(visitor_text=collect)
        for left, right in ((36, 204), (222, 390), (408, 576)):
            self.assertTrue(any(left <= x < right for x in positions), positions)
        ingredient_positions = []
        def collect_recipe_ingredients(text, cm, tm, font, size):
            if 'ingredient' in text:
                ingredient_positions.append(cm[4] + tm[4])
        for page in pages[first_recipe_page:-1]:
            page.extract_text(visitor_text=collect_recipe_ingredients)
        self.assertTrue(any(x < 300 for x in ingredient_positions))
        self.assertTrue(any(x > 300 for x in ingredient_positions))
        recipe_text = ''.join(page.extract_text() for page in pages[first_recipe_page:-1])
        for i in range(100):
            self.assertIn(f'1 cup ingredient {i}\n', recipe_text)
        recipe_pages = pages[first_recipe_page:-1]
        self.assertGreater(len(recipe_pages), 1)
        for index, page in enumerate(recipe_pages, 1):
            self.assertIn(f'Page {index}\n', page.extract_text())
            footer_text = []
            def collect_footer(text, cm, tm, font, size):
                if cm[5] + tm[5] < 70:
                    footer_text.append(text)
            page.extract_text(visitor_text=collect_footer)
            self.assertIn(first['title'], ''.join(footer_text))
        self.assertIn('Second recipe', pages[-1].extract_text())
        self.assertIn('Page 1\n', pages[-1].extract_text())

    def test_footer_title_and_page_number_align(self):
        for title in ('Short recipe', 'A longer recipe title with delicious ingredients ' * 4):
            with self.subTest(title=title):
                recipe = {**self.recipe, 'title': title}
                with patch('app.main.get_recipes', return_value=[recipe]):
                    response = self.client.post('/api/meal-plan/pdf', json={'recipes': [{'id': 7}]})
                page = PdfReader(BytesIO(response.content)).pages[1]
                footer_lines = []
                def collect(text, cm, tm, font, size):
                    y = cm[5] + tm[5] * cm[3]
                    if text.strip() and y < 90:
                        footer_lines.append((text.strip(), y))
                page.extract_text(visitor_text=collect)
                number_y = next(y for text, y in footer_lines if text == 'Page 1')
                title_y = next(y for text, y in footer_lines if text.startswith("Recipe: "))
                self.assertAlmostEqual(number_y, title_y, places=3)
                self.assertGreaterEqual(title_y, 36)
                self.assertGreaterEqual(number_y, 36)
                link_y = next(y for text, y in footer_lines if text.startswith('Link:'))
                self.assertLess(link_y, title_y)
                self.assertGreaterEqual(link_y, 36)

    def test_ingredient_prices_removed_at_original_and_scaled_servings(self):
        recipe = {**self.recipe, 'ingredients': ['2 cups broth ($0.50)', 'salt, to taste ($0.02)']}
        for servings in (2, 4):
            with self.subTest(servings=servings), patch('app.main.get_recipes', return_value=[recipe]):
                response = self.client.post('/api/meal-plan/pdf', json={
                    'recipes': [{'id': 7, 'servings': servings}]})
                self.assertEqual(response.status_code, 200)
                pages = PdfReader(BytesIO(response.content)).pages
                for page in pages:
                    self.assertNotIn('$', page.extract_text())
                self.assertIn(f'{servings} cups broth', pages[1].extract_text())
                self.assertIn('salt, to taste', pages[1].extract_text())

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


class PdfFractionTests(unittest.TestCase):
    def test_all_supported_fractions_use_available_glyphs(self):
        for symbol, quantity in UNICODE_FRACTIONS.items():
            with self.subTest(symbol=symbol):
                self.assertAlmostEqual(parse_ingredient(f"{symbol} cup milk")["quantity"], quantity)
                text = pdf_text(f"1{symbol} cups milk")
                self.assertTrue(text.startswith("1 "))
                self.assertNotIn(symbol, text)
                for font in ("Export", "ExportBold"):
                    self.assertTrue(all(ord(char) in pdfmetrics.getFont(font).face.charToGlyph for char in text))

    def test_third_cup_milk_in_printed_recipe_and_instructions(self):
        recipe = {"id": 7, "title": "Classic Meatloaf", "servings": 4,
                  "ingredients": ["⅓ cup milk", "1⅓ cups breadcrumbs"],
                  "instructions": ["Mix in ⅓ cup milk."], "source_url": "https://example.com/meatloaf"}
        client = TestClient(app)
        for servings, expected in ((4, "1/3 cup milk"), (8, "0.667 cup milk")):
            with self.subTest(servings=servings), patch('app.main.get_recipes', return_value=[recipe]):
                response = client.post('/api/meal-plan/pdf', json={"recipes": [{"id": 7, "servings": servings}]})
                self.assertEqual(response.status_code, 200)
                pages = PdfReader(BytesIO(response.content)).pages
                text = ''.join(page.extract_text() for page in pages[1:])
                self.assertIn(expected, text)
                self.assertIn("Mix in 1/3 cup milk.", text)
                self.assertNotIn("⅓", text)
                if servings == 4:
                    self.assertIn("1 1/3 cups breadcrumbs", text)
        self.assertEqual(recipe["ingredients"][0], "⅓ cup milk")

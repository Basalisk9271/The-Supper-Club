import unittest
from app.grocery import build_grocery_list, ingredient_category


class GroceryCategoryTests(unittest.TestCase):
    def test_common_ingredients_and_compound_names(self):
        examples = {
            'whole milk': 'Dairy & Eggs', 'large eggs': 'Dairy & Eggs',
            'chicken breasts': 'Meat & Seafood', 'ground beef': 'Meat & Seafood',
            'carrots, chopped': 'Vegetables', 'red bell pepper': 'Vegetables',
            'green beans': 'Vegetables', 'lemons': 'Fruit',
            'brown rice': 'Bakery & Grains', 'chicken broth': 'Pantry',
            'coconut milk': 'Pantry', 'peanut butter': 'Pantry',
            'garlic powder': 'Herbs & Spices', 'ground black pepper': 'Herbs & Spices',
            'canned tomatoes': 'Pantry', 'frozen spinach': 'Frozen',
            'cooking magic': 'Other', 'eggplant': 'Vegetables',
        }
        for ingredient, category in examples.items():
            with self.subTest(ingredient=ingredient):
                self.assertEqual(ingredient_category(ingredient), category)

    def test_sections_preserve_scaling_merging_and_alphabetical_order(self):
        recipes = [
            {'id': 1, 'title': 'First', 'servings': 2, 'ingredients': ['1 cup milk', '2 carrots', '1 onion', '1 tsp cumin']},
            {'id': 2, 'title': 'Second', 'servings': 1, 'ingredients': ['1 cup milk']},
        ]
        items = build_grocery_list(recipes, {'1': {'servings': 4}})
        self.assertEqual([x['category'] for x in items], ['Vegetables', 'Vegetables', 'Dairy & Eggs', 'Herbs & Spices'])
        self.assertEqual([x['name'] for x in items[:2]], ['carrots', 'onion'])
        self.assertEqual(items[2]['quantity'], 3)
        self.assertEqual(items[2]['sources'], ['First', 'Second'])
        self.assertFalse(items[2]['checked'])
        self.assertEqual(build_grocery_list([], {}), [])

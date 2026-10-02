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


class GroceryWeightTests(unittest.TestCase):
    def build(self, ingredients, servings=2):
        return build_grocery_list([
            {"id": 1, "title": "Dinner", "servings": 2, "ingredients": ingredients}
        ], {"1": {"servings": servings}})

    def test_pasta_and_dairy_pounds_become_ounces(self):
        for name in ["pasta", "spaghetti", "penne", "rigatoni", "cream cheese", "cheddar", "butter", "yogurt"]:
            for unit in ["lb", "lbs.", "pound", "pounds"]:
                with self.subTest(name=name, unit=unit):
                    item = self.build([f"1/2 {unit} {name}"])[0]
                    self.assertEqual((item["quantity_display"], item["unit"]), ("8", "oz"))

    def test_mixed_weight_units_merge_before_serving_scaling(self):
        recipes = [
            {"id": 1, "title": "Pasta night", "servings": 2, "ingredients": ["1 lb pasta"]},
            {"id": 2, "title": "Lunch", "servings": 2, "ingredients": ["8 ounces pasta"]},
        ]
        items = build_grocery_list(recipes, {"1": {"servings": 4}})
        self.assertEqual(len(items), 1)
        self.assertEqual((items[0]["quantity_display"], items[0]["unit"]), ("40", "oz"))
        self.assertEqual(items[0]["sources"], ["Lunch", "Pasta night"])

    def test_volume_counts_and_other_food_weights_stay_distinct(self):
        for line, expected in [
            ("1 cup milk", (1, "cup")), ("2 tbsp butter", (2, "tbsp")),
            ("2 eggs", (2, None)), ("1 lb ground beef", (1, "lb")),
            ("1 lb potatoes", (1, "lb")), ("1 lb pasta sauce", (1, "lb")),
            ("250 g pasta", (250, "g")), ("1 package cream cheese", (1, "package")),
        ]:
            with self.subTest(line=line):
                item = self.build([line])[0]
                self.assertEqual((item["quantity"], item["unit"]), expected)
        self.assertEqual(len(self.build(["1 cup cheddar", "1 lb cheddar"])), 2)

import unittest
from app.grocery import build_grocery_list, ingredient_category, parse_ingredient


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

    def test_cracked_pepper_is_a_spice_and_fresh_peppers_are_vegetables(self):
        examples = {
            'freshly cracked pepper': 'Herbs & Spices',
            'cracked pepper': 'Herbs & Spices',
            'freshly cracked black pepper': 'Herbs & Spices',
            'freshly ground pepper': 'Herbs & Spices',
            'fresh red bell pepper': 'Vegetables',
            'green peppers': 'Vegetables',
        }
        for name, category in examples.items():
            with self.subTest(name=name):
                self.assertEqual(ingredient_category(name), category)
        recipe = {'id': 1, 'title': 'Dinner', 'servings': 2,
                  'ingredients': ['1 tsp freshly cracked pepper']}
        self.assertEqual(build_grocery_list([recipe], {})[0]['category'], 'Herbs & Spices')

    def test_sections_preserve_scaling_merging_and_alphabetical_order(self):
        recipes = [
            {'id': 1, 'title': 'First', 'servings': 2, 'ingredients': ['1 cup milk', '2 carrots', '1 onion', '1 tsp cumin']},
            {'id': 2, 'title': 'Second', 'servings': 1, 'ingredients': ['1 cup milk']},
        ]
        items = build_grocery_list(recipes, {'1': {'servings': 4}})
        self.assertEqual([x['category'] for x in items], ['Vegetables', 'Vegetables', 'Dairy & Eggs', 'Herbs & Spices'])
        self.assertEqual([x['name'] for x in items[:2]], ['carrot', 'onion'])
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


class GroceryWaterTests(unittest.TestCase):
    def test_plain_water_is_omitted_without_changing_recipe_ingredients(self):
        ingredients = ["2 cups water", "Water", "1 cup hot water", "1 cup cold water",
                       "1 cup boiling water", "1 cup warm water, divided",
                       "water as needed", "1 cup water (for cooking)", "1 cup tap water"]
        recipe = {"id": 1, "title": "Dinner", "servings": 2, "ingredients": ingredients[:]}
        self.assertEqual(build_grocery_list([recipe], {"1": {"servings": 4}}), [])
        self.assertEqual(recipe["ingredients"], ingredients)

    def test_specific_water_types_and_other_ingredients_are_kept(self):
        ingredients = ["1 cup sparkling water", "1 cup distilled water", "1 cup coconut water",
                       "1 cup mineral water", "1 cup rose water", "1 cup water (distilled)",
                       "1 cup water, sparkling", "1 cup water chestnuts", "1 cup milk"]
        recipe = {"id": 1, "title": "Dinner", "servings": 2, "ingredients": ingredients}
        items = build_grocery_list([recipe], {"1": {"servings": 4}})
        self.assertEqual(len(items), len(ingredients))
        self.assertTrue(all(item["quantity"] == 2 for item in items))


class ExpandedCategoryTests(unittest.TestCase):
    def test_expanded_vocabulary_and_compound_precedence(self):
        examples = {
            "Meat & Seafood": ["boneless, skinless chicken breasts", "boneless, skinless, chicken breasts",
                               "(boneless skinless) chicken thighs", "pancetta", "sirloin", "halibut",
                               "cajun chicken", "chicken, served with rice"],
            "Herbs & Spices": ["cayenne powder", "ground ginger", "dry mustard", "garam masala",
                               "five-spice", "bay leaf", "fennel seeds", "sesame seeds", "cajun seasoning"],
            "Pantry": ["chicken stock", "fish sauce", "tahini", "gochujang", "rice milk", "almond butter",
                       "sunflower seeds", "dried cranberries", "canned chickpeas", "pasta sauce"],
            "Dairy & Eggs": ["mascarpone", "gruyère", "paneer", "kefir", "egg yolks"],
            "Bakery & Grains": ["rigatoni", "gnocchi", "naan", "puff pastry", "polenta"],
            "Vegetables": ["bok choy", "okra", "water chestnuts", "fresh oregano", "haricots verts",
                           "fresh sage", "sugar snap peas"],
            "Fruit": ["blackberries", "nectarines", "clementines", "papaya", "honeydew"],
            "Frozen": ["frozen green peas", "frozen chicken breasts", "sorbet", "tater tots"],
            "Other": ["mystery ingredient", "breadfruit extract", "saltwater magic"],
        }
        for category, names in examples.items():
            for name in names:
                with self.subTest(name=name):
                    self.assertEqual(ingredient_category(name), category)

    def test_attached_units_and_reported_ingredients_scale_and_sort(self):
        recipe = {"id": 1, "title": "Dinner", "servings": 2,
                  "ingredients": ["1lb boneless, skinless chicken breasts", "1tsp cayenne powder"]}
        items = build_grocery_list([recipe], {"1": {"servings": 4}})
        self.assertEqual([item["category"] for item in items], ["Meat & Seafood", "Herbs & Spices"])
        self.assertEqual([(item["quantity"], item["unit"]) for item in items], [(2, "lb"), (2, "tsp")])
        for text, quantity, unit in [("1lb chicken", 1, "lb"), ("250g pasta", 250, "g"),
                                     ("1/2cup milk", .5, "cup"), ("1½cups milk", 1.5, "cups")]:
            with self.subTest(text=text):
                parsed = parse_ingredient(text)
                self.assertEqual((parsed["quantity"], parsed["unit"]), (quantity, unit))


class GroceryGroupingTests(unittest.TestCase):
    def build(self, ingredients):
        return build_grocery_list([
            {"id": 1, "title": "Dinner", "servings": 2, "ingredients": ingredients}
        ], {"1": {"servings": 4}})

    def test_pepper_variations_merge_and_scale(self):
        items = self.build(["1 tsp freshly cracked pepper",
                            "1/2 tsp freshly cracked black pepper",
                            "1/4 tsp black pepper (freshly cracked)",
                            "1 tsp freshly ground black pepper"])
        self.assertEqual(len(items), 1)
        self.assertEqual((items[0]["name"], items[0]["quantity"], items[0]["unit"]),
                         ("black pepper", 5.5, "tsp"))

    def test_preparation_plural_and_unit_variations(self):
        for ingredients, name, unit in [
            (["1 cup finely chopped onions", "2 cups onion, diced"], "onion", "cup"),
            (["1 cup freshly grated parmesan", "2 cups parmesan (grated)"], "parmesan", "cup"),
            (["1 clove minced garlic", "2 cloves garlic, minced"], "garlic", "clove"),
        ]:
            with self.subTest(name=name):
                items = self.build(ingredients)
                self.assertEqual(len(items), 1)
                self.assertEqual((items[0]["name"], items[0]["quantity"], items[0]["unit"]),
                                 (name, 6, unit))

    def test_distinct_products_and_incompatible_units_stay_separate(self):
        ingredients = ["1 tsp black pepper", "1 tsp white pepper", "1 tsp red pepper flakes",
                       "1 red bell pepper", "1 cup fresh basil", "1 cup dried basil",
                       "1 cup butter", "1 cup unsalted butter", "1 lb ground beef", "1 lb beef",
                       "1 tbsp black pepper"]
        self.assertEqual(len(self.build(ingredients)), len(ingredients))

    def test_unmeasured_notes_and_recipe_sources_are_preserved(self):
        recipes = [
            {"id": 1, "title": "First", "ingredients": ["freshly cracked pepper to taste"]},
            {"id": 2, "title": "Second", "ingredients": ["black pepper (freshly cracked)"]},
        ]
        item, = build_grocery_list(recipes, {})
        self.assertEqual(item["name"], "black pepper")
        self.assertIsNone(item["quantity"])
        self.assertEqual(item["sources"], ["First", "Second"])
        self.assertEqual(item["notes"], [r["ingredients"][0] for r in recipes])

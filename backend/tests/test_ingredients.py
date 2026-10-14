import json
import unittest

from app.db import row_to_recipe
from app.ingredients import strip_ingredient_prices


class IngredientPriceTests(unittest.TestCase):
    def test_prices_removed_and_preparation_preserved(self):
        for line, expected in (
            ("2 cups broth ($0.50)", "2 cups broth"),
            ("1 onion (diced) ($1.25)", "1 onion (diced)"),
            ("salt, to taste ($0.02)", "salt, to taste"),
            ("1 (14 oz.) can tomatoes $1.50", "1 (14 oz.) can tomatoes"),
            ("½ cup milk", "½ cup milk"),
            ("1 onion* ($1.25)", "1 onion"),
            ("2 cups broth ($0.50*)", "2 cups broth"),
            ("salt (**$0.02**)", "salt"),
            ("• 1 onion† [$1.25]", "1 onion"),
            ("1 onion — $1.25", "1 onion"),
            ("1 onion* , diced", "1 onion, diced"),
            ("1 (14 oz.) can tomatoes, drained*", "1 (14 oz.) can tomatoes, drained"),
        ):
            with self.subTest(line=line):
                self.assertEqual(strip_ingredient_prices(line), expected)

    def test_saved_recipes_cleaned_without_changing_serving_cost(self):
        recipe = row_to_recipe({
            "ingredients_json": json.dumps(["1 onion ($1.25)"]),
            "instructions_json": "[]", "tags_json": "[]",
            "cost_text": "$2.50 recipe / $1.25 serving",
        })
        self.assertEqual(recipe["ingredients"], ["1 onion"])
        self.assertEqual(recipe["cost_text"], "$2.50 recipe / $1.25 serving")

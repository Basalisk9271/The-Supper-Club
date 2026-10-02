import unittest
from unittest.mock import patch

import httpx

from app import scraper


def card(slug, title, cost=''):
    href = slug if slug.startswith("https://") else "/" + slug
    return f'''<article class="post-summary"><a href="{href}">
    <img src="/food.jpg"><h3 class="post-summary__title">{title}</h3>
    {f'<span class="cost-per">{cost}</span>' if cost else ''}
    </a></article>'''


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        scraper._browse_category_page.cache_clear()

    def discover(self, html):
        client = httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text=html, request=request)))
        with patch.object(scraper, '_client', return_value=client):
            return scraper.browse_budget_bytes()['items']

    def test_only_recipe_cards_and_no_duplicates(self):
        html = '<a href="/sign-in/">Sign in</a><a href="/sign-up/">Sign up</a>'
        html += '<a href="/roundup/">Dinner Ideas</a>'
        html += card('soup/?utm_source=email#recipe', 'Soup', '$2.00 recipe')
        html += card('soup/', 'Soup', '$2.00 recipe')
        html += card('category/recipes/', 'All Recipes', '$2.00 recipe')
        html += card('https://example.com/soup/', 'External', '$2.00 recipe')
        with patch.object(scraper, '_is_recipe_page') as check:
            items = self.discover(html)
        check.assert_not_called()
        self.assertEqual([x['title'] for x in items], ['Soup'])
        self.assertEqual(items[0]['url'], 'https://www.budgetbytes.com/soup/')
        self.assertEqual(items[0]['image_url'], 'https://www.budgetbytes.com/food.jpg')

    def test_roundups_rejected_and_recipes_without_prices_kept(self):
        html = card('potato-recipes/', 'Easy Potato Recipes')
        html += card('casserole/', 'Breakfast Casserole')
        with patch.object(scraper, '_is_recipe_page', side_effect=[False, True]):
            self.assertEqual([x['title'] for x in self.discover(html)], ['Breakfast Casserole'])

    def test_unverifiable_card_skipped(self):
        with patch.object(scraper, '_is_recipe_page', side_effect=httpx.ConnectError('offline')):
            self.assertEqual(self.discover(card('roundup/', 'Dinner Ideas')), [])

    def test_fills_thirty_recipes_across_source_pages_without_duplicates(self):
        first = ''.join(card(f'recipe-{i}/', f'Recipe {i}', '$2 recipe') for i in range(20))
        first += '<a rel="nofollow" href="/category/recipes/page/2/">Next Page</a>'
        second = ''.join(card(f'recipe-{i}/', f'Recipe {i}', '$2 recipe') for i in range(15, 45))
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=second if '/page/2/' in request.url.path else first)))
        with patch.object(scraper, '_client', side_effect=lambda: httpx.Client(transport=client._transport)):
            one = scraper.browse_budget_bytes()
            two = scraper.browse_budget_bytes(page=2)
        self.assertEqual(len(one['items']), 30)
        self.assertTrue(one['has_more'])
        self.assertEqual(len(two['items']), 15)
        self.assertFalse(two['has_more'])
        self.assertFalse({x['url'] for x in one['items']} & {x['url'] for x in two['items']})

    def test_schema_validation_and_cache(self):
        scraper._is_recipe_page.cache_clear()
        self.addCleanup(scraper._is_recipe_page.cache_clear)
        with patch.object(scraper, 'fetch_recipe', return_value={
            'ingredients': ['1 egg'], 'instructions': ['Cook egg']
        }) as fetch:
            self.assertTrue(scraper._is_recipe_page('https://www.budgetbytes.com/egg/'))
            self.assertTrue(scraper._is_recipe_page('https://www.budgetbytes.com/egg/'))
            fetch.assert_called_once()
        with patch.object(scraper, 'fetch_recipe', return_value={'ingredients': [], 'instructions': []}):
            self.assertFalse(scraper._is_recipe_page('https://www.budgetbytes.com/roundup/'))


if __name__ == '__main__':
    unittest.main()

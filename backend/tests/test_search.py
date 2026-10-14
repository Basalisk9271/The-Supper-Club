import unittest
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from app import main, scraper

BASE = 'https://www.budgetbytes.com/'


class SearchTests(unittest.TestCase):
    def test_catalog_reads_all_post_sitemaps_and_caches(self):
        ns = 'http://www.sitemaps.org/schemas/sitemap/0.9'
        index = f'<sitemapindex xmlns="{ns}">' + ''.join(f'<sitemap><loc>{url}</loc></sitemap>' for url in [BASE+'post-sitemap.xml', BASE+'post-sitemap2.xml', BASE+'page-sitemap.xml', 'https://example.com/post-sitemap.xml']) + '</sitemapindex>'
        pages = {scraper.SITEMAP_INDEX:index, BASE+'post-sitemap.xml':f'<urlset xmlns="{ns}"><url><loc>{BASE}pancakes/</loc></url></urlset>', BASE+'post-sitemap2.xml':f'<urlset xmlns="{ns}"><url><loc>{BASE}banana-pancakes/</loc></url><url><loc>{BASE}pancakes/</loc></url></urlset>'}
        requests=[]
        def respond(request):
            requests.append(str(request.url))
            return httpx.Response(200, text=pages[str(request.url)])
        with patch.object(scraper, '_catalog_urls', ()), patch.object(scraper, '_catalog_expires', 0), patch.object(scraper, '_client', return_value=httpx.Client(transport=httpx.MockTransport(respond))):
            first=scraper._budget_bytes_catalog()
            self.assertEqual(set(first), {BASE+'pancakes/', BASE+'banana-pancakes/'})
            self.assertEqual(scraper._budget_bytes_catalog(), first)
        self.assertEqual(len(requests), 3)

    def test_plural_matching_pagination_and_roundup_exclusion(self):
        urls=[BASE+'pancakes/', BASE+'banana-pancake/', BASE+'pancake-collection/', BASE+'chicken/']
        def card(url, day):
            return None if 'collection' in url else {'title':url, 'url':url}
        with patch.object(scraper, '_budget_bytes_catalog', return_value=urls), patch.object(scraper, '_search_recipe_card', side_effect=card), patch.object(scraper, 'SEARCH_PAGE_SIZE', 2):
            first=scraper.search_budget_bytes(' PANCAKES ')
            self.assertEqual(len(first['items']), 2)
            self.assertFalse(first['has_more'])
            second=scraper.search_budget_bytes('pancake', 2)
            self.assertEqual(second['items'], [])
            self.assertFalse(second['has_more'])
            self.assertEqual(len(scraper.search_budget_bytes('banana pancakes')['items']), 1)

    def test_thirty_verified_recipes_per_page(self):
        urls = [BASE + f'pancakes-{i:02}/' for i in range(40)]
        def card(url, day):
            return None if url.endswith('00/') else {'title': url, 'url': url}
        with patch.object(scraper, '_budget_bytes_catalog', return_value=urls), patch.object(scraper, '_search_recipe_card', side_effect=card):
            one = scraper.search_budget_bytes('pancakes')
            two = scraper.search_budget_bytes('pancakes', 2)
        self.assertEqual(len(one['items']), 30)
        self.assertTrue(one['has_more'])
        self.assertEqual(len(two['items']), 9)
        self.assertFalse(two['has_more'])
        self.assertFalse({x['url'] for x in one['items']} & {x['url'] for x in two['items']})

    def test_only_structured_recipes_returned_and_cached(self):
        scraper._search_recipe_card.cache_clear()
        self.addCleanup(scraper._search_recipe_card.cache_clear)
        recipe={'title':'Pancakes','source_url':BASE+'pancakes/', 'source':'budgetbytes.com','ingredients':['flour'], 'instructions':['Cook']}
        with patch.object(scraper, 'fetch_recipe', return_value=recipe) as fetch:
            self.assertEqual(scraper._search_recipe_card(BASE+'pancakes/', 1)['title'], 'Pancakes')
            scraper._search_recipe_card(BASE+'pancakes/', 1)
            fetch.assert_called_once()
        with patch.object(scraper, 'fetch_recipe', return_value={'ingredients':[], 'instructions':[]}):
            self.assertIsNone(scraper._search_recipe_card(BASE+'roundup/', 1))

    def test_failures_are_reported_and_empty_query_does_not_fetch(self):
        with patch.object(scraper, '_budget_bytes_catalog', return_value=[BASE+'pancakes/']) as catalog, patch.object(scraper, '_search_recipe_card', side_effect=httpx.ConnectError('offline')):
            self.assertEqual(scraper.search_budget_bytes('!!!')['items'], [])
            catalog.assert_not_called()
            result=scraper.search_budget_bytes('pancakes')
            self.assertEqual(result['unavailable_count'], 1)
            self.assertEqual(result['items'], [])

    def test_discovery_api_routes_search_and_browse(self):
        client=TestClient(main.app)
        with patch.object(main, 'search_budget_bytes', return_value={'items':[]}) as search, patch.object(main, 'browse_budget_bytes', return_value={'items':[]}) as browse:
            self.assertEqual(client.get('/api/discover?q=pancakes&page=2').status_code, 200)
            search.assert_called_once_with('pancakes', 2)
            browse.assert_not_called()
            client.get('/api/discover?q=%20&category=Quick')
            browse.assert_called_once_with('Quick', 1)
            browse.reset_mock()
            client.get('/api/discover')
            browse.assert_called_once_with('New & Noteworthy', 1)

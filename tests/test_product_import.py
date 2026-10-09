import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import MagicMock, patch

import requests

from core import parse_ingredients
from product_import import extract_product, fetch_product, validate_url, ImportError, MAX_PAGE_BYTES


class ImportTests(unittest.TestCase):
    def test_matas_embedded_product_tab_removes_ph_and_label_disclaimer(self):
        model = {'model': {'productInformation': {
            'name': 'Matas Striber Shampoo 250 ml', 'brand': {'name': 'Matas Striber'},
            'productTabs': [{'type': 'Ingredients', 'content': {'blocks': [
                {'showAllText': True, 'content': 'Aqua, Glycerin, Citric Acid.pH-værdi: Ca. 5, 2'},
                {'showAllText': False, 'content': 'OBS: Check the physical product.'},
            ]}}]}}}
        html = f'<script type="module">React.createElement(Components.ProductPage, {json.dumps(model)});</script>'
        result = extract_product(html, 'https://www.matas.dk/shampoo')
        self.assertEqual(result.brand, 'Matas Striber')
        self.assertEqual(result.name, 'Matas Striber Shampoo 250 ml')
        self.assertEqual(parse_ingredients(result.raw), ['citric acid', 'glycerin', 'water'])

    def test_structured_product_brand_and_full_list(self):
        product = {'@type': 'Product', 'name': 'Shampoo & care',
                   'brand': {'@type': 'Brand', 'name': 'Test brand'},
                   'additionalProperty': [{'name': 'Ingredients', 'value':
                       'Aqua, Menthol, Glycerin, Extract (A, B), 1,2-Hexanediol'}]}
        html = f'<script type="application/ld+json">{json.dumps({"@graph": [product]})}</script>'
        result = extract_product(html, 'https://shop.example/shampoo')
        self.assertEqual(result.name, 'Shampoo & care')
        self.assertEqual(result.brand, 'Test brand')
        self.assertEqual(parse_ingredients(result.raw),
                         ['1,2-hexanediol', 'extract (a, b)', 'glycerin', 'menthol', 'water'])
        self.assertEqual(result.source_url, 'https://shop.example/shampoo')

    def test_danish_accordion_and_microdata_brand(self):
        html = '<h1>Shampoo til tør hovedbund</h1><span itemprop="brand">Dansk brand</span>' \
               '<details><summary>Ingredienser</summary><p>Aqua, Glycerin, Menthol</p></details>'
        result = extract_product(html, 'https://shop.example/dk')
        self.assertEqual(result.name, 'Shampoo til tør hovedbund')
        self.assertEqual(result.brand, 'Dansk brand')
        self.assertEqual(parse_ingredients(result.raw), ['glycerin', 'menthol', 'water'])

    def test_korean_table_and_heading_sections_preserve_original_labels(self):
        result = extract_product('<h1>두피 샴푸</h1><table><tr><th>전성분</th>'
                                 '<td>정제수, 글리세린, 멘톨</td></tr></table>',
                                 'https://shop.example/kr')
        self.assertEqual(result.name, '두피 샴푸')
        self.assertEqual(parse_ingredients(result.raw), ['글리세린', '멘톨', '정제수'])
        result = extract_product('<h1>Shampoo</h1><h2>Ingredients</h2><p>Aqua, Glycerin</p>'
                                 '<h2>How to use</h2><p>Massage, rinse</p>',
                                 'https://shop.example/product')
        self.assertEqual(result.raw, 'Aqua, Glycerin')

    def test_specific_product_selected_instead_of_recommendations(self):
        products = [{'@type': 'Product', 'name': 'Other', 'url': '/other', 'ingredients': 'Water, Menthol'},
                    {'@type': 'Product', 'name': 'Right', 'url': '/right', 'ingredients': ['Aqua', 'Glycerin']}]
        result = extract_product(f'<script type="application/ld+json">{json.dumps(products)}</script>',
                                 'https://shop.example/right')
        self.assertEqual(result.name, 'Right')
        with self.assertRaisesRegex(ImportError, 'several products'):
            extract_product(f'<script type="application/ld+json">{json.dumps(products)}</script>',
                            'https://shop.example/category')

    def test_missing_truncated_key_only_and_conflicting_lists_are_not_guessed(self):
        for html in ('<h1>Shampoo</h1><p>Contains soothing ingredients</p>',
                     '<div class="ingredients">Key ingredients: Tea Tree Oil, Glycerin</div>',
                     '<h2>Ingredients</h2><p>Water, Glycerin...</p>',
                     '<script type="application/ld+json">bad json</script><h1>Shampoo</h1>'):
            with self.subTest(html=html), self.assertRaisesRegex(ImportError, 'No clear full'):
                extract_product(html, 'https://shop.example')
        with self.assertRaisesRegex(ImportError, 'Several different ingredient lists'):
            extract_product('<div id="ingredients">Water, Glycerin</div>'
                            '<div class="product-ingredients">Water, Menthol</div>', 'https://shop.example')

    def test_url_validation(self):
        for value in ('', 'shop.example', 'file:///etc/passwd', 'ftp://shop.example',
                      'https://user:password@shop.example', 'https://shop.example:bad'):
            with self.subTest(value=value), self.assertRaises(ImportError):
                validate_url(value)
        self.assertEqual(validate_url(' https://shop.example/product '), 'https://shop.example/product')

    def test_fetch_errors_redirect_validation_and_size_limit(self):
        with patch('product_import.requests.Session') as session:
            client = session.return_value.__enter__.return_value
            client.get.side_effect = requests.Timeout()
            with self.assertRaisesRegex(ImportError, 'Could not read'):
                fetch_product('https://shop.example')
        for response_values, message in (
            ({'status_code': 302, 'headers': {'Location': 'file:///secret'}}, 'http://'),
            ({'status_code': 200, 'headers': {'Content-Type': 'application/pdf'}}, 'HTML'),
            ({'status_code': 200, 'headers': {'Content-Type': 'text/html'},
              'iter_content.return_value': [b'x' * (MAX_PAGE_BYTES + 1)]}, 'too large'),
        ):
            with self.subTest(message=message), patch('product_import.requests.Session') as session:
                response = MagicMock()
                response.configure_mock(**response_values)
                response.__enter__.return_value = response
                session.return_value.__enter__.return_value.get.return_value = response
                with self.assertRaisesRegex(ImportError, message):
                    fetch_product('https://shop.example')

    def test_http_fetch_redirect_and_charset_end_to_end(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                if self.path == '/redirect':
                    self.send_response(302)
                    self.send_header('Location', '/shampoo')
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write('<h1>두피 샴푸</h1><h2>전성분</h2><p>정제수, 글리세린</p>'.encode())

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            result = fetch_product(f'http://127.0.0.1:{server.server_port}/redirect')
            self.assertEqual(result.name, '두피 샴푸')
            self.assertEqual(result.raw, '정제수, 글리세린')
            self.assertTrue(result.source_url.endswith('/shampoo'))
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

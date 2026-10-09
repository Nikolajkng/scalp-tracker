"""Read product metadata and explicitly labeled ingredient lists from web pages."""
import json
from html import unescape
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from core import parse_ingredients

MAX_PAGE_BYTES = 3 * 1024 * 1024
INGREDIENT_LABEL = re.compile(
    r'^(?:ingredients?(?:\s*/\s*inci)?|inci(?:\s*(?:list|ingredients))?|'
    r'full ingredients|ingredienser|indholdsstoffer|전성분|'
    r'화장품법에\s*따라\s*기재[·ㆍ・/]\s*표시하여야\s*하는\s*모든\s*성분)\s*:?\s*$', re.I)
STOP_LABEL = re.compile(
    r'^(?:directions|how to use|usage|warnings|description|delivery|reviews|'
    r'please note|ingredients may|always check|anvendelse|brugsanvisning)\b', re.I)


class ImportError(ValueError):
    """A page could not be imported reliably."""


@dataclass
class ImportedProduct:
    name: str
    brand: str
    raw: str
    source_url: str
    warnings: tuple = ()


def validate_url(url):
    url = url.strip()
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ImportError('Enter a valid product URL.') from exc
    if (parsed.scheme not in ('https', 'http') or not parsed.hostname
            or parsed.username or parsed.password or port == 0):
        raise ImportError('Use a complete http:// or https:// product link without login details.')
    return url


def _text(value):
    if isinstance(value, str):
        text = BeautifulSoup(value, 'html.parser').get_text(' ') if '<' in value else unescape(value)
        return ' '.join(text.split())
    if isinstance(value, dict):
        return _text(value.get('name') or value.get('value') or '')
    return ''


def _products(value):
    if isinstance(value, list):
        for item in value:
            yield from _products(item)
    elif isinstance(value, dict):
        types = value.get('@type', [])
        if 'Product' in ([types] if isinstance(types, str) else types):
            yield value
        for key in ('@graph', 'mainEntity'):
            yield from _products(value.get(key))


def _ingredient_text(value):
    if isinstance(value, list):
        return ', '.join(filter(None, (_text(item) for item in value)))
    if isinstance(value, str):
        return BeautifulSoup(value, 'html.parser').get_text('\n', strip=True) if '<' in value else unescape(value)
    return _text(value)


def _clean_ingredients(text):
    # Retailer ingredient fields sometimes append pH and label disclaimers.
    text = re.split(r'\b(?:pH[- ]?(?:værdi|value)?\s*:|OBS\s*:)', text,
                    maxsplit=1, flags=re.I)[0]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    result = []
    for line in lines:
        if INGREDIENT_LABEL.fullmatch(line):
            continue
        line = re.sub(r'^(?:ingredients?|inci|ingredienser|indholdsstoffer|전성분)\s*:\s*',
                      '', line, flags=re.I)
        if STOP_LABEL.match(line):
            break
        result.append(line)
    raw = '\n'.join(result).strip()
    # A full stop appended to the list is punctuation, except known INCI
    # abbreviations. Keep ellipses so truncated lists are rejected below.
    if raw.endswith('.') and not raw.endswith('...') and not raw.lower().endswith('denat.'):
        raw = raw[:-1]
    return raw


def _usable_list(raw):
    # Reject prose-only, truncated, or excessively large extracts.
    return (len(raw) <= 12000 and '...' not in raw and '…' not in raw
            and len(parse_ingredients(raw)) >= 2
            and any(separator in raw for separator in (',', ';', '\n')))


def extract_product(html, source_url):
    """Extract a single product, failing when no clear full ingredient list exists."""
    soup = BeautifulSoup(html, 'html.parser')
    products = []
    if urlsplit(source_url).hostname in ('www.matas.dk', 'matas.dk'):
        for script in soup.find_all('script'):
            match = re.search(r'React\.createElement\(Components\.ProductPage,\s*',
                              script.get_text())
            if not match:
                continue
            try:
                data, _ = json.JSONDecoder().raw_decode(script.get_text()[match.end():])
                info = data['model']['productInformation']
                blocks = [block for tab in info.get('productTabs', [])
                          if tab.get('type') == 'Ingredients'
                          for block in tab.get('content', {}).get('blocks', [])
                          if block.get('showAllText')]
                products.append({'@type': 'Product', 'name': info.get('name'),
                                 'brand': info.get('brand'), 'url': source_url,
                                 'ingredients': '\n'.join(_ingredient_text(block.get('content'))
                                                         for block in blocks)})
                break
            except (ValueError, TypeError, KeyError):
                continue
    for script in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        try:
            products.extend(_products(json.loads(script.get_text())))
        except (ValueError, TypeError):
            continue
    # Prefer the product matching the supplied/canonical URL on multi-product pages.
    canonical = soup.find('link', rel='canonical')
    page_urls = {source_url.rstrip('/')}
    if canonical and canonical.get('href'):
        page_urls.add(urljoin(source_url, canonical['href']).rstrip('/'))
    matching = [p for p in products if
                urljoin(source_url, _text(p.get('url'))).rstrip('/') in page_urls
                and p.get('url')]
    if len(matching) == 1:
        products = matching
    if len(products) > 1:
        raise ImportError('This page contains several products. Use a link to one specific shampoo.')
    product = products[0] if products else {}
    meta = {}
    for tag in soup.find_all('meta'):
        meta[(tag.get('property') or tag.get('name') or '').lower()] = tag.get('content', '')
    heading = soup.find('h1')
    name = _text(product.get('name')) or (heading.get_text(' ', strip=True) if heading else '')
    name = name or meta.get('og:title', '') or (soup.title.get_text(' ', strip=True) if soup.title else '')
    brand_node = soup.find(attrs={'itemprop': 'brand'})
    brand = (_text(product.get('brand')) or meta.get('product:brand', '')
             or (brand_node.get('content') or brand_node.get_text(' ', strip=True) if brand_node else ''))
    candidates = []
    for key in ('ingredients', 'ingredient', 'hasIngredient'):
        if product.get(key):
            candidates.append(_clean_ingredients(_ingredient_text(product[key])))
    properties = product.get('additionalProperty', [])
    if isinstance(properties, dict):
        properties = [properties]
    for prop in properties:
        if isinstance(prop, dict) and INGREDIENT_LABEL.fullmatch(_text(prop.get('name'))):
            candidates.append(_clean_ingredients(_ingredient_text(prop.get('value'))))
    # Exclude navigation and executable content from visible-page extraction.
    for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'noscript']):
        tag.decompose()
    if not any(_usable_list(raw) for raw in candidates):
        for node in soup.find_all(['section', 'div', 'p', 'details', 'td', 'dd']):
            marker = ' '.join([node.get('id', ''), *node.get('class', [])])
            if re.search(r'(?:^|[-_\s])(?:ingredients?|inci)(?:$|[-_\s])', marker, re.I):
                # "Key ingredients" sections may be incomplete.
                text = node.get_text('\n', strip=True)
                if not re.search(r'\b(?:key|active|selected|featured) ingredients\b', text, re.I):
                    candidates.append(_clean_ingredients(text))
        for label in soup.find_all(['h2', 'h3', 'h4', 'h5', 'strong', 'b', 'summary', 'dt', 'th', 'span', 'p']):
            if not INGREDIENT_LABEL.fullmatch(label.get_text(' ', strip=True)):
                continue
            if label.name == 'summary' and label.parent.name == 'details':
                candidates.append(_clean_ingredients(label.parent.get_text('\n', strip=True)))
                continue
            chunks = []
            for sibling in label.next_siblings:
                if getattr(sibling, 'name', None) in ('h1', 'h2', 'h3', 'h4', 'h5'):
                    break
                text = sibling.get_text('\n', strip=True) if hasattr(sibling, 'get_text') else str(sibling).strip()
                if STOP_LABEL.match(text):
                    break
                chunks.append(text)
            candidates.append(_clean_ingredients('\n'.join(chunks)))
    valid = {}
    for raw in candidates:
        if _usable_list(raw):
            valid.setdefault(tuple(parse_ingredients(raw)), raw)
    if not valid:
        raise ImportError('No clear full ingredient list was found. The page may hide it behind '
                          'JavaScript, block automated access, or only list highlighted ingredients. '
                          'Copy the full list into Add product instead.')
    if len(valid) > 1:
        raise ImportError('Several different ingredient lists were found. Check the product variant '
                          'and copy the correct full list into Add product.')
    warnings = ['Check the variant and full list against the bottle before saving.']
    if not brand:
        warnings.append('The page did not identify a brand; enter it during review.')
    if not name:
        warnings.append('The page did not identify a product name; enter it during review.')
    return ImportedProduct(name, brand, next(iter(valid.values())), source_url, tuple(warnings))


def fetch_product(url):
    """Fetch HTML with TLS checks, timeouts, redirect and download limits."""
    url = validate_url(url)
    try:
        with requests.Session() as session:
            for _ in range(6):
                with session.get(url, timeout=(10, 20), stream=True, allow_redirects=False,
                                 headers={'User-Agent': 'ScalpTracker/1.2 (product ingredient import)',
                                          'Accept': 'text/html,application/xhtml+xml'}) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get('Location')
                        if not location:
                            raise ImportError('The page returned an invalid redirect.')
                        url = validate_url(urljoin(url, location))
                        continue
                    # A punctuation mark copied after a Matas link can become
                    # part of the path. Retry the actual slug only after a 404.
                    if response.status_code == 404 and urlsplit(url).hostname == 'www.matas.dk' and url.endswith('.'):
                        url = url[:-1]
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get('Content-Type', '').lower()
                    if not any(kind in content_type for kind in ('text/html', 'application/xhtml+xml')):
                        raise ImportError('The link must point to an HTML product page, not a file.')
                    body = bytearray()
                    for chunk in response.iter_content(65536):
                        body.extend(chunk)
                        if len(body) > MAX_PAGE_BYTES:
                            raise ImportError('The page is too large to import.')
                    # Let the parser honor HTML charset declarations, with HTTP
                    # charset as an explicit fallback when provided.
                    encoding = response.encoding if 'charset=' in content_type else None
                    html = BeautifulSoup(bytes(body), 'html.parser', from_encoding=encoding)
                    return extract_product(str(html), url)
            raise ImportError('The page redirected too many times.')
    except requests.RequestException as exc:
        raise ImportError('Could not read this page. Check the link and internet connection; '
                          'the website may block automated access.') from exc

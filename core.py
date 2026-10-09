"""Persistence and descriptive comparisons. Only Python's standard library."""
import csv
import re
import sqlite3
import unicodedata
from datetime import date
from pathlib import Path

ALIASES = {
    'aqua': 'water', 'eau': 'water', 'aqua (water)': 'water',
    'water (aqua)': 'water', 'water (aqua/eau)': 'water',
    'parfum': 'fragrance', 'perfume': 'fragrance',
    'parfum (fragrance)': 'fragrance', 'fragrance (parfum)': 'fragrance',
}
OUTCOMES = ('Unknown / not assessed', 'Tolerated', 'Reaction')
CONTAINERS = ('Unknown', 'Original bottle', 'Decanted bottle')

# User-selected label tags, independent of diary outcomes and comparisons.
NEGATIVE_INGREDIENTS = {
    'menthol', 'peppermint oil', 'cornmint oil', 'tea tree oil',
    'mentha piperita oil', 'mentha piperita leaf oil',
    'mentha arvensis oil', 'mentha arvensis leaf oil',
    'mentha canadensis oil', 'mentha canadensis leaf oil',
    'melaleuca alternifolia oil', 'melaleuca alternifolia leaf oil',
    '4-terpineol', 'terpinen-4-ol',
    '멘톨', '페퍼민트오일', '페퍼민트잎오일', '콘민트오일',
    '티트리잎오일', '티트리오일', '4-터피네올',
}
INVESTIGATE_INGREDIENTS = {
    'rosmarinus officinalis leaf oil', 'salvia rosmarinus leaf oil',
    'rosemary oil', 'rosemary leaf oil',
    'eucalyptus leaf oil', 'eucalyptus oil', 'eucalyptus globulus leaf oil',
    'eucalyptus globulus oil', 'eucalyptus radiata leaf oil',
    'capsicum fruit extract', 'capsicum annuum fruit extract',
    'capsicum frutescens fruit extract',
    '로즈마리잎오일', '로즈마리오일', '유칼립투스잎오일', '고추열매추출물',
}
POSITIVE_INGREDIENTS = {
    'glycerin', 'glycerine', 'glycerol', 'colloidal oatmeal',
    'oatmeal (colloidal)', 'pyrithione zinc', 'zinc pyrithione',
}

CATEGORY_DESCRIPTIONS = {
    'Oils': 'Plant oils and other explicitly named oils; useful for comparing formula composition.',
    'Fragrance': 'Perfume labels, common fragrance components and aromatic oils.',
    'Anti-fungals': 'Recognized antifungal actives. Presence alone does not establish dose or effectiveness.',
    'Cleansers': 'Common surfactants that help remove oil and dirt.',
    'Moisture support': 'Common humectants that help retain moisture.',
    'Barrier support': 'Ceramides and common barrier lipids.',
    'Soothing ingredients': 'Common soothing ingredients such as colloidal oatmeal and allantoin.',
    'Preservatives': 'Common preservatives used to protect the formula.',
    'pH adjusters': 'Ingredients commonly used to adjust or buffer formula pH.',
    'Texture / conditioning': 'Common thickeners, conditioning agents and silicones.',
    'Solvents': 'Common carriers and solvents such as water and alcohol.',
    'Other / unclassified': 'No rule matched. This is not a safety or effectiveness judgment.',
}
CATEGORY_LABELS = {
    'Fragrance': {'fragrance', 'limonene', 'linalool', 'citral', 'geraniol',
                  'citronellol', 'eugenol', 'coumarin', 'hexyl cinnamal',
                  'benzyl salicylate', 'menthol', '멘톨', '4-terpineol',
                  'terpinen-4-ol', '4-터피네올'},
    'Anti-fungals': {'zinc pyrithione', 'pyrithione zinc', 'piroctone olamine',
                    'climbazole', 'ketoconazole', 'selenium sulfide',
                    'selenium disulfide', 'ciclopirox', 'ciclopirox olamine'},
    'Cleansers': {'sodium lauryl sulfate', 'sodium laureth sulfate',
                 'ammonium lauryl sulfate', 'ammonium laureth sulfate',
                 'sodium coco-sulfate', 'sodium c14-16 olefin sulfonate',
                 'sodium lauryl sulfoacetate', 'cocamidopropyl betaine',
                 'coco-betaine', 'decyl glucoside', 'coco-glucoside',
                 'lauryl glucoside', 'sodium cocoyl isethionate',
                 'sodium cocoyl glutamate', 'disodium cocoyl glutamate',
                 'sodium lauroyl sarcosinate', 'disodium laureth sulfosuccinate'},
    'Moisture support': {'glycerin', 'glycerine', 'glycerol', 'panthenol',
                        'propylene glycol', 'butylene glycol', 'betaine',
                        'sodium pca', 'sodium hyaluronate', 'hyaluronic acid',
                        'urea', 'sorbitol'},
    'Barrier support': {'cholesterol', 'phytosphingosine', 'sphingosine'},
    'Soothing ingredients': {'colloidal oatmeal', 'oatmeal (colloidal)', 'allantoin',
                            'bisabolol', 'panthenol'},
    'Preservatives': {'phenoxyethanol', 'sodium benzoate', 'potassium sorbate',
                     'methylisothiazolinone', 'methylchloroisothiazolinone',
                     'benzyl alcohol', 'methylparaben', 'propylparaben',
                     'ethylparaben', 'dmdm hydantoin', 'chlorphenesin'},
    'pH adjusters': {'citric acid', 'sodium citrate', 'lactic acid',
                     'sodium hydroxide', 'potassium hydroxide'},
    'Texture / conditioning': {'sodium chloride', 'xanthan gum', 'carbomer',
                              'hydroxyethylcellulose', 'guar hydroxypropyltrimonium chloride',
                              'dimethicone', 'amodimethicone', 'cetyl alcohol',
                              'cetearyl alcohol', 'stearyl alcohol'},
    'Solvents': {'water', 'alcohol', 'alcohol denat.', 'ethanol', 'isopropyl alcohol'},
}


def ingredient_categories(name):
    """Conservative label-based grouping; an ingredient can have several roles."""
    name = normalize_lines([name])[0] if name.strip() else ''
    base = ' '.join(re.sub(r'\([^)]*\)', '', name).split())
    categories = {category for category, labels in CATEGORY_LABELS.items()
                  if name in labels or base in labels
                  or base.replace('sulphate', 'sulfate') in labels}
    if re.search(r'\boil$', base) or base in {
        '페퍼민트오일', '페퍼민트잎오일', '콘민트오일', '티트리잎오일',
        '티트리오일', '로즈마리잎오일', '로즈마리오일', '유칼립투스잎오일',
    }:
        categories.add('Oils')
    if ('Oils' in categories and base in NEGATIVE_INGREDIENTS | INVESTIGATE_INGREDIENTS):
        categories.add('Fragrance')
    if re.fullmatch(r'ceramides?(?: [a-z0-9]+(?:-[a-z0-9]+)*)?', base):
        categories.add('Barrier support')
    if re.fullmatch(r'polyquaternium-\d+', base):
        categories.add('Texture / conditioning')
    return tuple(category for category in CATEGORY_DESCRIPTIONS if category in categories) or ('Other / unclassified',)


def ingredient_flag(name):
    """Match explicit English/INCI labels; never infer health effects."""
    name = ' '.join(unicodedata.normalize('NFKC', name).casefold().split())
    # Parenthesized common names often accompany botanical INCI names.
    base = ' '.join(re.sub(r'\([^)]*\)', '', name).split())
    if (name in NEGATIVE_INGREDIENTS or base in NEGATIVE_INGREDIENTS
            or re.search(r'\b(?:sulfates?|sulphates?)$', base)):
        return 'Reacted'
    if name in INVESTIGATE_INGREDIENTS or base in INVESTIGATE_INGREDIENTS:
        return 'Investigate'
    if (name in POSITIVE_INGREDIENTS or base in POSITIVE_INGREDIENTS
            or re.fullmatch(r'ceramides?(?: [a-z0-9]+(?:-[a-z0-9]+)*)?', base)):
        return 'Neutral'
    return ''


def ingredient_flag_counts(names):
    """Count each reviewed, normalized ingredient once."""
    flags = [ingredient_flag(name) for name in normalize_lines(names)]
    return {'negative': flags.count('Reacted'), 'positive': flags.count('Neutral'),
            'investigate': flags.count('Investigate'),
            'total': len(flags)}


def product_recommendation(history, ingredients):
    """Personal screening heuristic with direct diary tolerance taking priority.

    Penalize distinct screening tags rather than their fraction of the formula:
    adding unrelated ingredients must not dilute a screening priority.
    """
    reaction = tolerated = 0
    for entry in history:
        reaction += entry['outcome'] == 'Reaction'
        tolerated += entry['outcome'] == 'Tolerated'
    assessed = reaction + tolerated
    counts = ingredient_flag_counts(ingredients)
    screening_score = max(0, 100 - 20 * counts['negative'] - 10 * counts['investigate'])
    if assessed:
        # Ingredient screening can reduce observed tolerance by up to 25%.
        score = round(100 * tolerated / assessed * (0.75 + screening_score / 400), 1)
        basis = ('Mixed history' if reaction and tolerated else
                 'Reaction history' if reaction else 'Tolerated history')
    else:
        # An unassessed formula must not look empirically tolerated.
        score = round(0.6 * screening_score, 1)
        basis = 'Ingredients only'
    # Reserve 100 for history with zero reactions, even after display rounding.
    if reaction and score is not None:
        score = min(score, 99.9)
    return {'reaction': reaction, 'tolerated': tolerated, 'score': score,
            'basis': basis, 'screening_score': screening_score}


def parse_ingredients(raw):
    """Split only outside parentheses; keep original text in the product record.

    Never fuzzy-match chemistry names or split hyphens/slashes. The editable
    preview lets the user correct ambiguous commas such as 1,2-hexanediol.
    """
    raw = unicodedata.normalize('NFKC', raw).strip()
    raw = re.sub(r'^(ingredients|inci|전성분)\s*[:：]\s*', '', raw, flags=re.I)
    tokens, current, depth = [], [], 0
    for i, char in enumerate(raw):
        if char == '(':
            depth += 1
        elif char == ')':
            depth = max(0, depth - 1)
        numeric_comma = (char == ',' and i > 0 and i + 1 < len(raw)
                         and raw[i-1].isdigit() and raw[i+1].isdigit())
        if char in ',;\n\r' and depth == 0 and not numeric_comma:
            tokens.append(''.join(current))
            current = []
        else:
            current.append(char)
    tokens.append(''.join(current))
    return normalize_lines(tokens)


def normalize_lines(lines):
    result = set()
    for line in lines:
        name = ' '.join(unicodedata.normalize('NFKC', line).casefold().split())
        if name:
            result.add(ALIASES.get(name, name))
    return sorted(result)


class Store:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys = ON')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                brand TEXT NOT NULL, raw TEXT NOT NULL,
                notes TEXT NOT NULL, location TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ingredients (
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                name TEXT NOT NULL, PRIMARY KEY(product_id, name)
            );
            CREATE TABLE IF NOT EXISTS diary (
                id INTEGER PRIMARY KEY,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                used_on TEXT NOT NULL, observed_on TEXT NOT NULL,
                outcome TEXT NOT NULL, flakes INTEGER NOT NULL CHECK(flakes BETWEEN 0 AND 5),
                itch INTEGER NOT NULL CHECK(itch BETWEEN 0 AND 5),
                bumps INTEGER NOT NULL CHECK(bumps >= 0),
                container TEXT NOT NULL, notes TEXT NOT NULL
            );
        ''')
        if 'source_url' not in {row['name'] for row in self.db.execute('PRAGMA table_info(products)')}:
            self.db.execute("ALTER TABLE products ADD COLUMN source_url TEXT NOT NULL DEFAULT ''")
            self.db.commit()

    def products(self):
        return self.db.execute('SELECT * FROM products ORDER BY name, id').fetchall()

    def ingredients(self, product_id):
        return [r[0] for r in self.db.execute(
            'SELECT name FROM ingredients WHERE product_id=? ORDER BY name', (product_id,))]

    def save_product(self, name, brand, raw, ingredients, notes='', location='', product_id=None,
                     source_url=''):
        names = normalize_lines(ingredients)
        if not name.strip() or not raw.strip() or not names:
            raise ValueError('Provide a product name, original ingredients and reviewed ingredient names.')
        values = (name.strip(), brand.strip(), raw.strip(), notes.strip(), location.strip(), source_url.strip())
        with self.db:
            if product_id is None:
                product_id = self.db.execute(
                    'INSERT INTO products(name,brand,raw,notes,location,source_url) VALUES(?,?,?,?,?,?)', values).lastrowid
            else:
                self.db.execute('UPDATE products SET name=?,brand=?,raw=?,notes=?,location=?,source_url=? WHERE id=?',
                                values + (product_id,))
                self.db.execute('DELETE FROM ingredients WHERE product_id=?', (product_id,))
            self.db.executemany('INSERT INTO ingredients VALUES(?,?)', [(product_id, n) for n in names])
        return product_id

    def save_entry(self, product_id, used_on, observed_on, outcome, flakes, itch, bumps,
                   container, notes='', entry_id=None):
        used, observed = date.fromisoformat(used_on), date.fromisoformat(observed_on)
        if observed < used:
            raise ValueError('Observation date must be on or after the use date.')
        if outcome not in OUTCOMES or container not in CONTAINERS:
            raise ValueError('Choose a listed outcome and container.')
        flakes, itch, bumps = int(flakes), int(itch), int(bumps)
        if not (0 <= flakes <= 5 and 0 <= itch <= 5 and bumps >= 0):
            raise ValueError('Flakes and itch must be 0–5; bumps must be zero or greater.')
        values = (product_id, used.isoformat(), observed.isoformat(), outcome,
                  flakes, itch, bumps, container, notes.strip())
        with self.db:
            if entry_id is None:
                return self.db.execute('''INSERT INTO diary
                    (product_id,used_on,observed_on,outcome,flakes,itch,bumps,container,notes)
                    VALUES(?,?,?,?,?,?,?,?,?)''', values).lastrowid
            self.db.execute('''UPDATE diary SET product_id=?,used_on=?,observed_on=?,outcome=?,
                flakes=?,itch=?,bumps=?,container=?,notes=? WHERE id=?''', values + (entry_id,))
        return entry_id

    def entries(self):
        return self.db.execute('''SELECT d.*, p.name AS product FROM diary d
            JOIN products p ON p.id=d.product_id ORDER BY observed_on DESC, d.id DESC''').fetchall()

    def delete(self, kind, record_id):
        table = {'product': 'products', 'entry': 'diary'}[kind]
        with self.db:
            self.db.execute(f'DELETE FROM {table} WHERE id=?', (record_id,))

    def comparisons(self, symptom='Any reaction'):
        """Count distinct formulas and shared ingredient evidence across outcomes.

        Symptom comparisons only count user-labeled Reaction entries with the
        selected symptom. Tolerated is always explicit, never inferred from 0.
        Formulas with their own mixed history stay outside the percentage groups.
        """
        groups = {}
        reaction_products, tolerated_products = set(), set()
        symptom_column = {'Flakes': 'flakes', 'Itch': 'itch', 'Bumps': 'bumps'}.get(symptom)
        for p in self.products():
            entries = self.db.execute('SELECT * FROM diary WHERE product_id=?', (p['id'],)).fetchall()
            reaction = any(e['outcome'] == 'Reaction' and
                           (symptom_column is None or e[symptom_column] > 0) for e in entries)
            tolerated = any(e['outcome'] == 'Tolerated' for e in entries)
            if reaction:
                reaction_products.add(p['id'])
            if tolerated:
                tolerated_products.add(p['id'])
            # Other reactions prevent being classified as exclusively tolerated.
            other_reaction = any(e['outcome'] == 'Reaction' for e in entries)
            if tolerated and other_reaction:
                group = 'mixed'
            elif reaction:
                group = 'reaction'
            elif tolerated:
                group = 'tolerated'
            else:
                group = 'unknown'
            groups[p['id']] = group
        totals = {g: list(groups.values()).count(g) for g in ('reaction', 'tolerated', 'mixed', 'unknown')}
        counts = {}
        presence = {}
        for r in self.db.execute('SELECT * FROM ingredients'):
            item = counts.setdefault(r['name'], dict.fromkeys(totals, 0))
            item[groups[r['product_id']]] += 1
            presence.setdefault(r['name'], set()).add(r['product_id'])
        rows = []
        for name, c in counts.items():
            difference = (c['reaction']/totals['reaction'] - c['tolerated']/totals['tolerated']
                          if totals['reaction'] and totals['tolerated'] else None)
            # Shared evidence belongs to the ingredient, even if reaction and
            # tolerance were recorded for different formulas. Count each
            # assessed formula once; unknown formulas contribute no evidence.
            reaction_evidence = presence[name] & reaction_products
            tolerated_evidence = presence[name] & tolerated_products
            both_outcomes = (len(reaction_evidence | tolerated_evidence)
                             if reaction_evidence and tolerated_evidence else 0)
            rows.append({'name': name, **c, 'bottles': sum(c.values()),
                         'both_outcomes': both_outcomes, 'difference': difference})
        rows.sort(key=lambda r: (-(r['difference'] if r['difference'] is not None else -2),
                                 -r['reaction'], r['name']))
        return totals, rows

    def backup(self, destination):
        destination = Path(destination).expanduser().resolve()
        if destination == self.path:
            raise ValueError('Choose a different file from your active database.')
        with sqlite3.connect(destination) as target:
            self.db.backup(target)

    def export(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        for table in ('products', 'ingredients', 'diary'):
            cursor = self.db.execute(f'SELECT * FROM {table}')
            with (directory / f'{table}.csv').open('w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([c[0] for c in cursor.description])
                # Prevent spreadsheet formula execution in user-entered text.
                for row in cursor:
                    writer.writerow(["'" + v if isinstance(v, str) and v.lstrip().startswith(
                        ('=', '+', '-', '@')) else v for v in row])

    def close(self):
        self.db.close()

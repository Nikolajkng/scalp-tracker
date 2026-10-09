import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core import Store, parse_ingredients, ingredient_flag, ingredient_flag_counts


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.store = Store(self.path / 'test.sqlite3')

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def product(self, name, raw='Water, Parfum'):
        return self.store.save_product(name, '', raw, parse_ingredients(raw))

    def entry(self, pid, outcome='Reaction', flakes=2, **kw):
        args = dict(product_id=pid, used_on='2026-10-01', observed_on='2026-10-02',
                    outcome=outcome, flakes=flakes, itch=0, bumps=0, container='Unknown')
        args.update(kw)
        return self.store.save_entry(**args)

    def test_parser_preserves_chemistry_and_normalizes_known_aliases(self):
        self.assertEqual(parse_ingredients('Ingredients: Aqua; Parfum\n1,2-Hexanediol, Extract (A, B), PEG-7; 정제수'),
                         ['1,2-hexanediol', 'extract (a, b)', 'fragrance', 'peg-7', 'water', '정제수'])
        self.assertEqual(parse_ingredients('Water, AQUA, Eau'), ['water'])

    def test_user_ingredient_flags_match_labels_without_matching_other_chemicals(self):
        negative = [
            'MENTHOL', 'Peppermint Oil', 'Cornmint Oil', 'Tea Tree Oil',
            'Mentha Piperita (Peppermint) Oil', 'Mentha Arvensis Leaf Oil',
            'Melaleuca Alternifolia (Tea Tree) Leaf Oil',
            'Sodium Lauryl Sulfate', 'Sodium Laureth Sulphate',
            'Ammonium Lauryl Sulfate', 'Magnesium Sulfate',
        ]
        positive = [
            'Glycerin', 'Glycerine', 'Colloidal Oatmeal', 'Oatmeal (Colloidal)',
            'Ceramide NP', 'Ceramide AP', 'Ceramide EOP', 'Ceramide 3',
            'Ceramides', 'Pyrithione Zinc', 'Zinc Pyrithione',
        ]
        neutral = [
            'Water', 'Menthyl Lactate', 'Mentha Piperita Leaf Extract',
            'Melaleuca Alternifolia Leaf Extract', 'Sodium C14-16 Olefin Sulfonate',
            'Sodium Lauryl Sulfoacetate', 'Glyceryl Stearate', 'Glycereth-26',
            'Avena Sativa Kernel Extract', 'Zinc Oxide', 'Sulfate-free',
        ]
        for name in negative:
            with self.subTest(name=name):
                self.assertEqual(ingredient_flag(name), 'Negative')
        for name in positive:
            with self.subTest(name=name):
                self.assertEqual(ingredient_flag(name), 'Positive')
        for name in neutral:
            with self.subTest(name=name):
                self.assertEqual(ingredient_flag(name), '')
        self.assertEqual(ingredient_flag_counts(
            ['Water', 'Aqua', 'Glycerin', 'GLYCERIN', 'Menthol']),
            {'negative': 1, 'positive': 1, 'total': 3})

    def test_distinct_products_mixed_unknown_and_missing_comparator(self):
        a, b, c, d = [self.product(n) for n in ('A', 'B', 'C', 'D')]
        for _ in range(5):
            self.entry(a)
        self.entry(b, 'Tolerated', 0)
        self.entry(c)
        self.entry(c, 'Tolerated', 0)
        totals, rows = self.store.comparisons()
        self.assertEqual(totals, dict(reaction=1, tolerated=1, mixed=1, unknown=1))
        self.assertEqual(rows[0]['reaction'], 1)
        self.assertEqual(rows[0]['difference'], 0)
        self.assertEqual(rows[0]['bottles'], 4)
        # Repeated diary entries and symptom filters must not inflate bottle counts.
        self.assertTrue(all(row['bottles'] == 4 for row in self.store.comparisons('Bumps')[1]))
        self.store.delete('product', b)
        self.assertTrue(all(r['difference'] is None for r in self.store.comparisons()[1]))
        self.assertTrue(all(r['bottles'] == 3 for r in self.store.comparisons()[1]))

    def test_symptom_filter_and_unknown_not_assumed_tolerated(self):
        a, b = self.product('A'), self.product('B')
        self.entry(a, flakes=0, bumps=2)
        self.entry(b, 'Unknown / not assessed', 0)
        self.assertEqual(self.store.comparisons('Flakes')[0]['reaction'], 0)
        self.assertEqual(self.store.comparisons('Bumps')[0]['reaction'], 1)
        self.assertEqual(self.store.comparisons()[0]['tolerated'], 0)

    def test_difference_uses_group_denominators(self):
        a = self.product('A', 'Water, Parfum')
        b = self.product('B', 'Water')
        c = self.product('C', 'Water')
        self.entry(a)
        self.entry(b)
        self.entry(c, 'Tolerated', 0)
        rows = {r['name']: r for r in self.store.comparisons()[1]}
        self.assertEqual(rows['fragrance']['difference'], 0.5)
        self.assertEqual(rows['water']['difference'], 0)

    def test_edit_delete_and_cascade(self):
        pid = self.product('A')
        eid = self.entry(pid)
        self.entry(pid, 'Tolerated', 0, entry_id=eid)
        self.assertEqual(len(self.store.entries()), 1)
        self.assertEqual(self.store.comparisons()[0]['tolerated'], 1)
        self.store.save_product('B', 'Brand', 'Water', ['Water'], product_id=pid)
        self.assertEqual(self.store.ingredients(pid), ['water'])
        self.store.delete('product', pid)
        self.assertEqual(self.store.entries(), [])
        self.assertEqual(self.store.ingredients(pid), [])

    def test_validation(self):
        pid = self.product('A')
        for kw in ({'observed_on': '2026-09-30'}, {'flakes': 6}, {'bumps': -1},
                   {'outcome': 'typo'}, {'container': 'typo'}, {'used_on': 'not a date'}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                self.entry(pid, **kw)
        with self.assertRaises(sqlite3.IntegrityError):
            self.entry(999)
        self.assertEqual(self.store.entries(), [])

    def test_persistence_backup_and_csv(self):
        pid = self.product('=unsafe formula', 'Water, 정제수')
        self.entry(pid, notes='Multiline\nnotes, and commas')
        self.store.close()
        self.store = Store(self.path / 'test.sqlite3')
        self.assertEqual(len(self.store.entries()), 1)
        backup = self.path / 'backup.sqlite3'
        self.store.backup(backup)
        recovered = Store(backup)
        self.assertEqual(dict(recovered.entries()[0]), dict(self.store.entries()[0]))
        recovered.close()
        with self.assertRaises(ValueError):
            self.store.backup(self.store.path)
        self.store.export(self.path / 'export')
        with (self.path / 'export/products.csv').open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]['name'], "'=unsafe formula")
        self.assertEqual(rows[0]['raw'], 'Water, 정제수')


if __name__ == '__main__':
    unittest.main()

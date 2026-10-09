"""GUI regression smoke test: run on Linux with a display (or under Xvfb).

The core tests remain independent of CustomTkinter and the graphical desktop.
"""
import os
import sys
import tempfile
import unittest
import tkinter.font as tkfont
from pathlib import Path
from unittest.mock import patch


@unittest.skipUnless(os.environ.get('DISPLAY') or sys.platform in ('win32', 'darwin'),
                     'A graphical desktop is required for the GUI smoke test')
class GuiTests(unittest.TestCase):
    def test_startup_navigation_forms_and_tables(self):
        import customtkinter as ctk
        from app import App
        from core import Store

        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'smoke.sqlite3')
            app = App(store)
            errors = []
            app.report_callback_exception = lambda *error: errors.append(error)
            try:
                app.update()
                self.assertEqual(len(app.tables), 4)
                self.assertIn('Ingredient Categories', app.pages)
                self.assertNotIn('mixed', app.compare_tree['columns'])
                self.assertEqual(app.compare_tree.heading('unknown', 'text'), 'Not assessed')
                self.assertEqual(app.compare_tree.heading('difference', 'text'), 'Reaction Percentage')
                with patch('app.messagebox.showinfo') as info:
                    app.update()
                    info.assert_not_called()
                    app.comparison_info_button.invoke()
                    info.assert_called_once()
                    self.assertIn('percentage points', info.call_args.args[1])
                for mode in ('Light', 'Dark'):
                    app.change_theme(mode)
                    for name in app.pages:
                        app.show_tab(name)
                        app.update()

                # Form construction used to be hidden behind the startup crash.
                app.product_dialog()
                app.update()
                windows = [w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
                self.assertEqual(len(windows), 1)
                windows[0].destroy()

                pid = store.save_product('Long product name ' * 25, 'Test', 'Water, Glycerin', ['water', 'glycerin'])
                store.save_entry(pid, '2026-10-01', '2026-10-02', 'Reaction', 2, 0, 0, 'Original bottle')
                app.refresh()
                for name in app.pages:
                    app.show_tab(name)
                    app.update()
                app.entry_dialog()
                app.update()
                windows = [w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
                self.assertEqual(len(windows), 1)
                windows[0].destroy()
                for tree in app.tables:
                    tree.xview_moveto(1)
                    app.update()
                    tree.xview_moveto(0)
                app.geometry('980x720')
                app.update()
                body_font = tkfont.Font(family='sans-serif', size=11)
                self.assertGreaterEqual(app.product_tree.column('name', 'width'),
                                        body_font.measure(app.product_tree.set(str(pid), 'name')) + 28)
                self.assertLess(app.product_tree.xview()[1], 1)
                self.assertEqual(app.compare_tree.set('0', 'bottles'), '1')
                self.assertEqual(app.product_tree.set(str(pid), 'negative'), '0 / 2')
                self.assertEqual(app.product_tree.set(str(pid), 'positive'), '1 / 2')
                flags = {app.compare_tree.set(row, 'ingredient'): app.compare_tree.set(row, 'flag')
                         for row in app.compare_tree.get_children()}
                self.assertEqual(flags, {'water': '—', 'glycerin': 'Positive'})
                app.category.set('Moisture support')
                app.refresh_categories()
                self.assertEqual([app.category_tree.set(row, 'ingredient')
                                  for row in app.category_tree.get_children()], ['glycerin'])
                app.category.set('All categories')
                app.refresh_categories()
                self.assertEqual(len(app.category_tree.get_children()), 2)
                # Counts and individual flags update after formula edits.
                store.save_product('Short', 'Test', 'Menthol, Water, Glycerin',
                                   ['menthol', 'water', 'glycerin'], product_id=pid)
                app.refresh()
                self.assertEqual(app.product_tree.set(str(pid), 'negative'), '1 / 3')
                self.assertEqual(app.product_tree.set(str(pid), 'positive'), '1 / 3')
                flags = {app.compare_tree.set(row, 'ingredient'): app.compare_tree.set(row, 'flag')
                         for row in app.compare_tree.get_children()}
                self.assertEqual(flags['menthol'], 'Negative')
                # Short contents should fill the viewport, including after resize.
                store.save_product('Short', 'Test', 'Water, Glycerin',
                                   ['water', 'glycerin'], product_id=pid)
                app.refresh()
                for geometry in ('1180x840', '980x720'):
                    app.geometry(geometry)
                    app.update()
                    for tree in app.tables:
                        width = sum(tree.column(c, 'width') for c in tree['columns'])
                        self.assertGreaterEqual(width, tree.winfo_width() - 2)
                    self.assertAlmostEqual(
                        sum(app.product_tree.column(c, 'width') for c in app.product_tree['columns']),
                        app.product_tree.winfo_width() - 2, delta=2)
                    self.assertEqual(app.product_tree.column('name', 'width'),
                                     max(60, body_font.measure('Product / formula') + 28,
                                         body_font.measure('Short') + 28,
                                         tkfont.Font(family='sans-serif', size=10, weight='bold')
                                         .measure('Product / formula') + 28))
                self.assertTrue(app.footer.winfo_ismapped())
                self.assertLessEqual(app.footer.winfo_y() + app.footer.winfo_height(), app.winfo_height())
                app.symptom.set('Flakes')
                app.refresh_comparison()
                app.update()
                self.assertEqual(errors, [], errors)
            finally:
                app.quit_app()

    def test_every_header_sorts_both_directions_and_refresh_preserves_order(self):
        from app import App
        from core import Store
        with tempfile.TemporaryDirectory() as directory:
            app = App(Store(Path(directory) / 'sort.sqlite3'))
            try:
                app.update()
                for tree in app.tables:
                    for column in tree['columns']:
                        tree.delete(*tree.get_children())
                        samples = (['+10.0 🚩', '-2.0 ✅', '—'] if column == 'difference'
                                   else ['10 / 12', '2 / 3', '30 / 40']
                                   if column in tree.numeric_columns else ['Zulu', 'alpha', 'Bravo'])
                        for value in samples:
                            tree.insert('', 'end', values=[
                                value if name == column else '' for name in tree['columns']])
                        # Invoke the actual header callback, as a click does.
                        tree.tk.call(tree.heading(column, 'command'))
                        ascending = [tree.set(row, column) for row in tree.get_children()]
                        expected = ([samples[1], samples[0], samples[2]] if column == 'difference'
                                    or column in tree.numeric_columns else
                                    [samples[1], samples[2], samples[0]])
                        self.assertEqual(ascending, expected, (tree, column))
                        tree.tk.call(tree.heading(column, 'command'))
                        descending = [tree.set(row, column) for row in tree.get_children()]
                        expected_descending = ([samples[0], samples[1], samples[2]]
                                               if column == 'difference' else list(reversed(expected)))
                        self.assertEqual(descending, expected_descending, (tree, column))
                        self.assertTrue(tree.heading(column, 'text').endswith('▼'))

                first = app.store.save_product('Zulu', '', 'Water', ['water'])
                second = app.store.save_product('Alpha', '', 'Glycerin', ['glycerin'])
                app.refresh()
                app.sort_table(app.product_tree, 'name', False)
                app.product_tree.selection_set(str(first))
                app.sort_table(app.product_tree, 'name')
                self.assertEqual(app.product_tree.selection(), (str(first),))
                app.refresh()
                self.assertEqual(app.product_tree.get_children(), (str(first), str(second)))
            finally:
                # Cancel callbacks belonging to this root before another test
                # creates its own Tk interpreter.
                for callback in app.tk.call('after', 'info'):
                    app.after_cancel(callback)
                app.quit_app()

"""GUI regression smoke test: run on Linux with a display (or under Xvfb).

The core tests remain independent of CustomTkinter and the graphical desktop.
"""
import os
import sys
import tempfile
import unittest
import tkinter.font as tkfont
from pathlib import Path


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
                self.assertEqual(len(app.tables), 3)
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

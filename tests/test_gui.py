"""GUI regression smoke test: run on Linux with a display (or under Xvfb).

The core tests remain independent of CustomTkinter and the graphical desktop.
"""
import os
import sys
import tempfile
import unittest
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
                self.assertLessEqual(app.product_tree.column('name', 'width'), 480)
                self.assertTrue(app.footer.winfo_ismapped())
                self.assertLessEqual(app.footer.winfo_y() + app.footer.winfo_height(), app.winfo_height())
                app.symptom.set('Flakes')
                app.refresh_comparison()
                app.update()
                self.assertEqual(errors, [], errors)
            finally:
                app.quit_app()

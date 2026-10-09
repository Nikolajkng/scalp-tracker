"""Run with: python app.py. Offline CustomTkinter desktop interface."""
import argparse
import re
import sqlite3
import tkinter as tk
import tkinter.font as tkfont
try:
    import customtkinter as ctk
except ImportError:
    raise SystemExit('CustomTkinter is missing. Run: python3 -m pip install -r requirements.txt')
from datetime import date, datetime
from pathlib import Path
from tkinter import ttk, messagebox, filedialog

from core import (Store, parse_ingredients, ingredient_flag, ingredient_flag_counts,
                  ingredient_categories, CATEGORY_DESCRIPTIONS, OUTCOMES, CONTAINERS)


def text_value(widget):
    return widget.get('1.0', 'end-1c').strip()


class App(ctk.CTk):
    def __init__(self, store):
        ctk.set_appearance_mode('dark')
        ctk.set_default_color_theme('blue')
        super().__init__()
        self.store = store
        self.tables = []
        self.table_sorts = {}
        self.title('Scalp Tracker')
        self.geometry('1180x840')
        self.minsize(980, 720)
        self.configure(fg_color=('#eef3f0', '#101916'))
        self.style = ttk.Style(self)
        self.style.theme_use('clam')

        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=28, pady=(24, 12))
        ctk.CTkLabel(header, text='SCALP JOURNAL', font=ctk.CTkFont(size=12, weight='bold'),
                     text_color=('#37785c', '#88c9aa')).pack(anchor='w')
        title_row = ctk.CTkFrame(header, fg_color='transparent')
        title_row.pack(fill='x')
        ctk.CTkLabel(title_row, text='A little clarity, one wash at a time.',
                     font=ctk.CTkFont(size=28, weight='bold')).pack(side='left')
        ctk.CTkOptionMenu(title_row, values=['Dark', 'Light'], width=110,
                          command=self.change_theme).pack(side='right')
        ctk.CTkLabel(header, text='Keep your formulas and observations together. Explore patterns at your own pace.',
                     text_color=('#597067', '#a6b8af')).pack(anchor='w', pady=(4, 0))

        self.stat_vars = [tk.StringVar(value='0') for _ in range(3)]
        # Own the navigation layout instead of rearranging CTkTabview internals.
        tab_names = ('Products', 'Reaction Diary', 'Ingredients Patterns', 'Ingredient Categories')
        navigation = ctk.CTkSegmentedButton(
            self, values=list(tab_names), height=76,
            font=ctk.CTkFont(size=17, weight='bold'), corner_radius=12,
            selected_color='#2563eb', selected_hover_color='#1d4ed8',
            command=self.show_tab)
        navigation.pack(fill='x', padx=28, pady=(8, 8))
        book = ctk.CTkFrame(self, corner_radius=16, fg_color=('#ffffff', '#1b2822'))
        book.grid_rowconfigure(0, weight=1)
        book.grid_columnconfigure(0, weight=1)
        self.pages = {}
        for name in tab_names:
            page = ctk.CTkFrame(book, fg_color='transparent')
            page.grid(row=0, column=0, sticky='nsew', padx=12, pady=12)
            self.pages[name] = page
        self.product_tab, self.diary_tab, self.compare_tab, self.category_tab = self.pages.values()
        navigation.set(tab_names[0])
        self.show_tab(tab_names[0])

        stats = ctk.CTkFrame(self, fg_color='transparent')
        for i, (label, var) in enumerate(zip(['PRODUCTS SAVED', 'OBSERVATIONS', 'INGREDIENTS TRACKED'], self.stat_vars)):
            stats.columnconfigure(i, weight=1)
            card = ctk.CTkFrame(stats, corner_radius=14, fg_color=('#ffffff', '#1b2822'))
            card.grid(row=0, column=i, sticky='ew', padx=(0 if i == 0 else 8, 0))
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=11, weight='bold'),
                         text_color=('#597067', '#a6b8af')).pack(anchor='w', padx=18, pady=(12, 0))
            ctk.CTkLabel(card, textvariable=var, font=ctk.CTkFont(size=27, weight='bold')).pack(anchor='w', padx=18, pady=(0, 12))
        self.build_products()
        self.build_diary()
        self.build_comparison()
        self.build_categories()
        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.pack(side='bottom', fill='x', padx=28, pady=(4, 20))
        self.footer = footer
        ctk.CTkButton(footer, text='Export CSV', width=115, command=self.export,
                      fg_color='#2563eb', hover_color='#1d4ed8').pack(side='right')
        ctk.CTkButton(footer, text='Back up database', width=150, command=self.backup,
                      fg_color='#2563eb', hover_color='#1d4ed8').pack(side='right', padx=8)
        self.status = tk.StringVar(value='Saved on this computer · Patterns, not a diagnosis')
        ctk.CTkLabel(footer, textvariable=self.status, wraplength=560, justify='left',
                     text_color=('#597067', '#a6b8af')).pack(side='left')
        # Reserve the footer and summary before giving remaining space to pages.
        stats.pack(side='bottom', fill='x', padx=28, pady=(0, 8))
        book.pack(fill='both', expand=True, padx=28, pady=(0, 8))
        self.protocol('WM_DELETE_WINDOW', self.quit_app)
        self.change_theme('Dark')
        self.refresh()

    def show_tab(self, name):
        self.pages[name].tkraise()

    def change_theme(self, mode):
        ctk.set_appearance_mode(mode)
        dark = mode == 'Dark'
        bg, fg = ('#1b2822', '#e1ece6') if dark else ('#ffffff', '#233a2e')
        heading = '#25382e' if dark else '#e5efe9'
        stripe = '#203027' if dark else '#f3f7f4'
        separator = '#ffffff'
        self.style.configure('Treeview', background=bg, fieldbackground=bg, foreground=fg,
                             borderwidth=0, rowheight=38, font=('sans-serif', 11))
        self.style.configure('Treeview.Heading', background=heading, foreground=fg,
                             relief='flat', font=('sans-serif', 10, 'bold'), padding=(10, 12))
        self.style.map('Treeview', background=[('selected', '#2563eb')], foreground=[('selected', '#ffffff')])
        self.style.map('Treeview.Heading', background=[('active', heading)])
        for tree in self.tables:
            tree.tag_configure('stripe', background=stripe)
        for line in getattr(self, 'table_separators', []):
            line.configure(background=separator)

    def guard(self, action):
        try:
            action()
        except (ValueError, sqlite3.Error, OSError) as exc:
            messagebox.showerror('Could not complete action', str(exc), parent=self)

    def table(self, parent, columns, labels, widths):
        frame = ctk.CTkFrame(parent, fg_color='transparent')
        frame.pack(fill='both', expand=True)
        tree = ttk.Treeview(frame, columns=columns, show='headings', selectmode='browse', height=7)
        numeric_columns = {
            'n', 'flakes', 'itch', 'bumps', 'reaction', 'tolerated',
            'mixed', 'unknown', 'difference', 'bottles', 'negative', 'positive',
        }
        tree.numeric_columns = numeric_columns.intersection(columns)
        for column, label, width in zip(columns, labels, widths):
            anchor = 'center' if column in numeric_columns else 'w'
            tree.heading(column, text=label, anchor=anchor,
                         command=lambda c=column: self.sort_table(tree, c))
            tree.column(column, width=width, minwidth=60, anchor=anchor, stretch=False)
        bar = ctk.CTkScrollbar(frame, orientation='vertical', command=tree.yview)
        tree.configure(yscrollcommand=bar.set)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky='nsew')
        bar.grid(row=0, column=1, sticky='ns')
        horizontal = ctk.CTkScrollbar(frame, orientation='horizontal', command=tree.xview)
        horizontal.grid(row=1, column=0, sticky='ew')
        if not hasattr(self, 'table_separators'):
            self.table_separators = []
        lines = []
        for _ in widths[:-1]:
            line = tk.Frame(tree, width=1, bg='#ffffff', borderwidth=0)
            line.place(x=0, y=0, relheight=1.0, anchor='nw')
            lines.append(line)
            self.table_separators.append(line)
        if not hasattr(self, 'table_specs'):
            self.table_specs = []
        self.table_specs.append((tree, frame, columns, labels, lines))
        def on_horizontal_scroll(first, last):
            horizontal.set(first, last)
            self.position_separators(tree, columns, lines)
        tree.configure(xscrollcommand=on_horizontal_scroll)
        tree.bind('<Configure>', lambda event: self.resize_table_columns(tree))
        tree.bind('<ButtonRelease-1>', lambda event: self.position_separators(tree, columns, lines), add='+')
        self.tables.append(tree)
        return tree

    def sort_table(self, tree, column, descending=None):
        if descending is None:
            previous_column, previous_descending = self.table_sorts.get(tree, (None, False))
            descending = not previous_descending if previous_column == column else False
        self.table_sorts[tree] = (column, descending)
        values, missing = [], []
        for item in tree.get_children():
            text = tree.set(item, column)
            if column in tree.numeric_columns:
                # Count fractions sort by their numerator; markers are ignored.
                match = re.match(r'^[+-]?\d+(?:\.\d+)?', text.strip())
                if match is None:
                    missing.append(item)
                    continue
                value = float(match.group())
            else:
                value = text.casefold()
            values.append((value, item))
        items = [item for _, item in sorted(values, key=lambda pair: pair[0], reverse=descending)]
        for index, item in enumerate(items + missing):
            tree.move(item, '', index)
        for table, _, columns, labels, _ in self.table_specs:
            if table is tree:
                for name, label in zip(columns, labels):
                    tree.heading(name, text=label + (' ▼' if descending else ' ▲') if name == column else label)
                break
        self.stripe_rows(tree)
        self.resize_table_columns(tree)

    def restore_table_sort(self, tree):
        if tree in self.table_sorts:
            self.sort_table(tree, *self.table_sorts[tree])
        else:
            self.stripe_rows(tree)
            self.resize_table_columns(tree)

    def position_separators(self, tree, columns, lines):
        total = sum(tree.column(column, 'width') for column in columns)
        offset = -round(tree.xview()[0] * total)
        for column, line in zip(columns, lines):
            offset += tree.column(column, 'width')
            if 0 < offset < tree.winfo_width() - 1:
                line.place(x=offset, y=0, relheight=1.0)
            else:
                line.place_forget()

    def resize_table_columns(self, tree):
        for table, frame, columns, labels, lines in getattr(self, 'table_specs', []):
            if table is not tree:
                continue
            body_font = tkfont.Font(family='sans-serif', size=11)
            heading_font = tkfont.Font(family='sans-serif', size=10, weight='bold')
            widths = []
            for column, label in zip(columns, labels):
                widest = heading_font.measure(tree.heading(column, 'text'))
                for item in tree.get_children():
                    widest = max(widest, body_font.measure(str(tree.set(item, column))))
                widths.append(max(60, widest + 28))
            # Preserve room for every value, scrolling when content is wider
            # than the viewport. The final column fills remaining row space.
            available = max(0, tree.winfo_width() - 2)
            extra = max(0, available - sum(widths))
            for index, (column, width) in enumerate(zip(columns, widths)):
                tree.column(column, minwidth=width,
                            width=width + (extra if index == len(columns) - 1 else 0))
            self.position_separators(tree, columns, lines)
            break

    def build_products(self):
        ctk.CTkLabel(self.product_tab, text='Add the exact formula from your label. Use a new product entry if the formula changes.',
                  wraplength=850).pack(anchor='w', pady=(0, 10))
        self.product_tree = self.table(self.product_tab,
            ('brand', 'name', 'n', 'negative', 'positive', 'location'),
            ('Brand', 'Product / formula', 'Ingredients', 'Negative ingredients', 'Positive ingredients', 'Bought at'),
            (170, 350, 90, 160, 160, 180))
        buttons = ctk.CTkFrame(self.product_tab, fg_color='transparent')
        buttons.pack(fill='x', pady=10)
        for text, command in [('Add product', lambda: self.product_dialog()),
                              ('Edit selected', self.edit_product), ('Delete selected', self.delete_product)]:
            ctk.CTkButton(buttons, text=text, command=command,
                          fg_color='#2563eb', hover_color='#1d4ed8').pack(side='left', padx=(0, 8))
        self.product_tree.bind('<Double-1>', lambda e: self.edit_product())
        self.product_empty = ctk.CTkLabel(self.product_tab, text='', text_color=('#597067', '#a6b8af'))
        self.product_empty.pack(anchor='w')
        ctk.CTkLabel(self.product_tab, text='Negative / positive counts show your tagged ingredients / total reviewed ingredients. '
                    'These are your chosen tags, not safety ratings.',
                  wraplength=850).pack(anchor='w')

    def selected(self, tree):
        values = tree.selection()
        if not values:
            messagebox.showinfo('Select a row', 'Select a row first.', parent=self)
            return None
        return int(values[0])

    def edit_product(self):
        pid = self.selected(self.product_tree)
        if pid is not None:
            self.product_dialog(next(p for p in self.store.products() if p['id'] == pid))

    def delete_product(self):
        pid = self.selected(self.product_tree)
        if pid is not None and messagebox.askyesno('Delete product?',
                'This deletes the product and all its diary entries. Continue?', parent=self):
            self.guard(lambda: (self.store.delete('product', pid), self.refresh()))

    def dialog(self, title):
        window = ctk.CTkToplevel(self)
        window.title(title)
        height = min(900, max(400, self.winfo_screenheight() - 100))
        window.geometry(f'820x{height}')
        window.minsize(720, min(500, height))
        window.transient(self)
        ctk.CTkLabel(window, text=title, font=ctk.CTkFont(size=24, weight='bold')).pack(
            anchor='w', padx=24, pady=(20, 8))
        frame = ctk.CTkScrollableFrame(window, corner_radius=12)
        frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        frame.columnconfigure(1, weight=1)
        window.wait_visibility()
        window.grab_set()
        return window, frame

    def field(self, frame, row, label, value='', options=None):
        ctk.CTkLabel(frame, text=label, justify='left').grid(row=row, column=0, sticky='w', padx=(8, 18), pady=7)
        var = tk.StringVar(value=value)
        widget = (ctk.CTkOptionMenu(frame, variable=var, values=list(options), width=380, dynamic_resizing=False)
                  if options is not None else ctk.CTkEntry(frame, textvariable=var, width=380, height=36))
        widget.grid(row=row, column=1, sticky='ew', padx=(0, 8), pady=7)
        if isinstance(widget, ctk.CTkEntry):
            widget.bind('<Control-a>', lambda event: (widget.select_range(0, 'end'), 'break')[-1])
        return var

    def textbox(self, frame, row, label, value='', height=4):
        ctk.CTkLabel(frame, text=label, justify='left').grid(row=row, column=0, sticky='nw', pady=7, padx=(8, 18))
        box = ctk.CTkTextbox(frame, width=400, height=height * 22 + 12, wrap='word', undo=True,
                             border_width=1, corner_radius=8)
        box.grid(row=row, column=1, sticky='nsew', pady=7, padx=(0, 8))
        box.insert('1.0', value)
        box.bind('<Control-a>', lambda event: (box.tag_add('sel', '1.0', 'end-1c'), 'break')[-1])
        return box

    def product_dialog(self, product=None):
        p = dict(product) if product is not None else {}
        window, frame = self.dialog('Edit product' if p else 'Add product')
        name = self.field(frame, 0, 'Product / formula *', p.get('name', ''))
        brand = self.field(frame, 1, 'Brand', p.get('brand', ''))
        location = self.field(frame, 2, 'Bought at', p.get('location', ''))
        raw = self.textbox(frame, 3, 'Original ingredients *', p.get('raw', ''), 5)
        reviewed = self.textbox(frame, 5, 'Reviewed ingredients *\nOne ingredient per line',
                                '\n'.join(self.store.ingredients(p['id'])) if p else '', 7)

        def preview():
            reviewed.delete('1.0', 'end')
            reviewed.insert('1.0', '\n'.join(parse_ingredients(text_value(raw))))
        ctk.CTkButton(frame, text='Parse list → review names below', command=preview,
                      fg_color='#2563eb', hover_color='#1d4ed8').grid(row=4, column=1, sticky='w')
        ctk.CTkLabel(frame, text='Check the preview before saving. English aliases are limited; Korean names remain unchanged.',
                  wraplength=480).grid(row=6, column=1, sticky='w')
        notes = self.textbox(frame, 7, 'Notes / label version', p.get('notes', ''), 3)

        def save():
            if p and (text_value(raw) != p['raw'] or
                      text_value(reviewed).splitlines() != self.store.ingredients(p['id'])):
                if not messagebox.askyesno('Update formula?',
                        'Existing diary entries will use these edited ingredients. For a reformulation, cancel and add a new product. Save this correction?',
                        parent=window):
                    return
            self.store.save_product(name.get(), brand.get(), text_value(raw),
                                    text_value(reviewed).splitlines(), text_value(notes), location.get(), p.get('id'))
            window.destroy()
            self.refresh()
        ctk.CTkButton(frame, text='Save product', command=lambda: self.guard(save),
                      fg_color='#2563eb', hover_color='#1d4ed8').grid(row=8, column=1, sticky='e', pady=8)

    def build_diary(self):
        ctk.CTkLabel(self.diary_tab, text='Log observed symptoms and context. “Tolerated” is your assessment; zero symptoms do not automatically mean tolerated.',
                  wraplength=850).pack(anchor='w', pady=(0, 10))
        self.diary_tree = self.table(self.diary_tab,
            ('date', 'product', 'outcome', 'flakes', 'itch', 'bumps', 'container'),
            ('Observed', 'Product', 'Assessment', 'Flakes', 'Itch', 'Bumps', 'Container'),
            (95, 230, 155, 60, 60, 60, 140))
        buttons = ctk.CTkFrame(self.diary_tab, fg_color='transparent')
        buttons.pack(fill='x', pady=10)
        for text, command in [('Add observation', lambda: self.entry_dialog()),
                              ('Edit selected', self.edit_entry), ('Delete selected', self.delete_entry)]:
            ctk.CTkButton(buttons, text=text, command=command,
                          fg_color='#2563eb', hover_color='#1d4ed8').pack(side='left', padx=(0, 8))
        self.diary_tree.bind('<Double-1>', lambda e: self.edit_entry())
        self.diary_empty = ctk.CTkLabel(self.diary_tab, text='', text_color=('#597067', '#a6b8af'))
        self.diary_empty.pack(anchor='w')

    def edit_entry(self):
        eid = self.selected(self.diary_tree)
        if eid is not None:
            self.entry_dialog(next(e for e in self.store.entries() if e['id'] == eid))

    def delete_entry(self):
        eid = self.selected(self.diary_tree)
        if eid is not None and messagebox.askyesno('Delete observation?', 'Delete this diary entry?', parent=self):
            self.guard(lambda: (self.store.delete('entry', eid), self.refresh()))

    def entry_dialog(self, entry=None):
        products = self.store.products()
        if not products:
            messagebox.showinfo('Add a product', 'Add a product on the Products tab first.', parent=self)
            return
        e = dict(entry) if entry is not None else {}
        window, frame = self.dialog('Edit observation' if e else 'Add observation')
        choices = {f"{p['name']} · {p['brand']} [#{p['id']}]": p['id'] for p in products}
        selected = next((k for k, v in choices.items() if v == e.get('product_id')), next(iter(choices)))
        product = self.field(frame, 0, 'Product', selected, list(choices))
        used = self.field(frame, 1, 'Used on (YYYY-MM-DD)', e.get('used_on', date.today().isoformat()))
        observed = self.field(frame, 2, 'Observed on (YYYY-MM-DD)', e.get('observed_on', date.today().isoformat()))
        outcome = self.field(frame, 3, 'Your assessment', e.get('outcome', OUTCOMES[0]), OUTCOMES)
        flakes = self.field(frame, 4, 'Flakes (0 none – 5 severe)', str(e.get('flakes', 0)), list(map(str, range(6))))
        itch = self.field(frame, 5, 'Itch (0 none – 5 severe)', str(e.get('itch', 0)), list(map(str, range(6))))
        bumps = self.field(frame, 6, 'Number of bumps', str(e.get('bumps', 0)))
        container = self.field(frame, 7, 'Container', e.get('container', CONTAINERS[0]), CONTAINERS)
        notes = self.textbox(frame, 8, 'Context / other symptoms', e.get('notes', ''), 6)
        ctk.CTkLabel(frame, text='Examples: pus, delay before symptoms, bottle cleaning, added water, other products, treatment, baseline symptoms.',
                  wraplength=460).grid(row=9, column=1, sticky='w')

        def save():
            self.store.save_entry(choices[product.get()], used.get(), observed.get(), outcome.get(),
                                  flakes.get(), itch.get(), bumps.get(), container.get(), text_value(notes), e.get('id'))
            window.destroy()
            self.refresh()
        ctk.CTkButton(frame, text='Save observation', command=lambda: self.guard(save),
                      fg_color='#2563eb', hover_color='#1d4ed8').grid(row=10, column=1, sticky='e', pady=8)

    def build_comparison(self):
        top = ctk.CTkFrame(self.compare_tab, fg_color='transparent')
        top.pack(fill='x')
        ctk.CTkLabel(top, text='Compare observations for:').pack(side='left')
        self.symptom = tk.StringVar(value='Any reaction')
        choice = ctk.CTkOptionMenu(top, variable=self.symptom, values=['Any reaction', 'Flakes', 'Itch', 'Bumps'],
                                   command=lambda value: self.refresh_comparison())
        choice.pack(side='left', padx=10)
        self.comparison_info_button = ctk.CTkButton(
            top, text='ⓘ', width=36, command=self.show_comparison_info)
        self.comparison_info_button.pack(side='right')
        self.summary = tk.StringVar()
        ctk.CTkLabel(self.compare_tab, textvariable=self.summary, wraplength=900).pack(anchor='w', pady=10)
        self.compare_tree = self.table(self.compare_tab,
            ('ingredient', 'flag', 'bottles', 'reaction', 'tolerated', 'unknown', 'difference'),
            ('Ingredient', 'Your flag', 'Bottles / formulas', 'Reaction', 'Tolerated', 'Not assessed', 'Reaction Percentage'),
            (270, 100, 140, 95, 95, 130, 170))
        self.compare_tree.bind('<<TreeviewSelect>>', self.ingredient_detail)
        self.detail = tk.StringVar(value='Select an ingredient to see which products contain it.')
        ctk.CTkLabel(self.compare_tab, textvariable=self.detail, wraplength=900).pack(anchor='w', pady=10)

    def show_comparison_info(self):
        messagebox.showinfo('About Reaction Percentage',
            'Reaction Percentage keeps the original comparison: the percentage of reaction-group '
            'products containing an ingredient minus the percentage of tolerated-group products containing it.\n\n'
            'Example: 2 / 4 reaction products and 1 / 4 tolerated products = 50% − 25% = +25 percentage points. '
            'It is not the probability of a reaction. A dash means a comparison group is missing. '
            '🚩 marks +20 points or higher; ✅ marks −20 points or lower.\n\n'
            'Bottles / formulas counts distinct saved products, not physical bottles or washes. '
            'Products with both reaction and tolerated observations remain excluded from the percentages. '
            'Not assessed includes products with no qualifying assessment for the selected symptom, '
            'including reactions only to another symptom.\n\n'
            'Your positive and negative flags are separate personal tags. These patterns do not '
            'account for concentration or other exposures and do not establish causation or safety.',
            parent=self)

    def build_categories(self):
        top = ctk.CTkFrame(self.category_tab, fg_color='transparent')
        top.pack(fill='x')
        ctk.CTkLabel(top, text='Ingredient category:').pack(side='left')
        self.category = tk.StringVar(value='All categories')
        self.category_menu = ctk.CTkOptionMenu(
            top, variable=self.category, values=['All categories', *CATEGORY_DESCRIPTIONS],
            width=240, command=lambda value: self.refresh_categories())
        self.category_menu.pack(side='left', padx=10)
        self.category_description = tk.StringVar()
        ctk.CTkLabel(self.category_tab, textvariable=self.category_description,
                    wraplength=900, justify='left').pack(anchor='w', pady=10)
        self.category_tree = self.table(self.category_tab,
            ('ingredient', 'category', 'flag', 'bottles'),
            ('Ingredient', 'Categories', 'Your flag', 'Bottles / formulas'),
            (300, 350, 100, 140))

    def refresh_categories(self):
        selected = self.category.get()
        self.category_description.set(CATEGORY_DESCRIPTIONS.get(selected,
            'Group ingredients by common roles. One ingredient can appear in several categories; '
            'unrecognized labels remain unclassified. Categories are not safety ratings.'))
        self.category_tree.delete(*self.category_tree.get_children())
        _, rows = self.store.comparisons()
        for row in rows:
            categories = ingredient_categories(row['name'])
            if selected != 'All categories' and selected not in categories:
                continue
            self.category_tree.insert('', 'end', values=(
                row['name'], ', '.join(categories), ingredient_flag(row['name']) or '—', row['bottles']))
        self.restore_table_sort(self.category_tree)

    def refresh_comparison(self):
        totals, rows = self.store.comparisons(self.symptom.get())
        self.compare_tree.delete(*self.compare_tree.get_children())
        self.comparison_rows = {}
        for index, row in enumerate(rows):
            key = str(index)
            self.comparison_rows[key] = row['name']
            if row['difference'] is None:
                difference = '—'
            else:
                points = 100 * row['difference']
                marker = ' 🚩' if points >= 20 else ' ✅' if points <= -20 else ''
                difference = f"{points:+.1f}{marker}"
            self.compare_tree.insert('', 'end', iid=key, values=(row['name'], ingredient_flag(row['name']) or '—', row['bottles'],
                f"{row['reaction']} / {totals['reaction']}", f"{row['tolerated']} / {totals['tolerated']}",
                row['unknown'], difference))
        suffix = ('Add explicitly tolerated and reaction observations to compare.'
                  if not totals['reaction'] or not totals['tolerated'] else 'Exploratory evidence only; no confidence or causal score.')
        self.summary.set(f"Products: {totals['reaction']} reaction · {totals['tolerated']} tolerated · "
                         f"{totals['mixed']} mixed (excluded) · {totals['unknown']} not assessed. {suffix}")
        self.restore_table_sort(self.compare_tree)
        self.detail.set('Select an ingredient to see which products contain it.')

    def ingredient_detail(self, event=None):
        selected = self.compare_tree.selection()
        if not selected or selected[0] not in self.comparison_rows:
            return
        name = self.comparison_rows[selected[0]]
        products = [p for p in self.store.products() if name in self.store.ingredients(p['id'])]
        lines = []
        entries = self.store.entries()
        for p in products:
            history = [e for e in entries if e['product_id'] == p['id']]
            reaction = sum(e['outcome'] == 'Reaction' for e in history)
            tolerated = sum(e['outcome'] == 'Tolerated' for e in history)
            lines.append(f"{p['name']} (#{p['id']}): {reaction} reaction, {tolerated} tolerated, {len(history)} total observations")
        self.detail.set(name + ' — ' + '; '.join(lines))

    def refresh(self):
        products, entries = self.store.products(), self.store.entries()
        ingredients = {name for p in products for name in self.store.ingredients(p['id'])}
        for var, value in zip(self.stat_vars, (len(products), len(entries), len(ingredients))):
            var.set(str(value))
        self.product_empty.configure(text='' if products else 'No products yet. Add your first shampoo to get started.')
        self.diary_empty.configure(text='' if entries else 'No observations yet. Add a product, then record your first observation.')
        self.product_tree.delete(*self.product_tree.get_children())
        for p in self.store.products():
            counts = ingredient_flag_counts(self.store.ingredients(p['id']))
            self.product_tree.insert('', 'end', iid=p['id'], values=(p['brand'], p['name'],
                counts['total'], f"{counts['negative']} / {counts['total']}",
                f"{counts['positive']} / {counts['total']}", p['location']))
        self.diary_tree.delete(*self.diary_tree.get_children())
        for e in self.store.entries():
            self.diary_tree.insert('', 'end', iid=e['id'], values=tuple(e[k] for k in
                ('observed_on', 'product', 'outcome', 'flakes', 'itch', 'bumps', 'container')))
        self.refresh_comparison()
        self.refresh_categories()
        for tree in self.tables:
            self.restore_table_sort(tree)

    def stripe_rows(self, tree):
        for index, item in enumerate(tree.get_children()):
            tree.item(item, tags=('stripe',) if index % 2 else ())

    def backup(self):
        path = filedialog.asksaveasfilename(parent=self, title='Save database backup',
            initialfile=f'scalp-backup-{date.today()}.sqlite3', defaultextension='.sqlite3')
        if path:
            self.guard(lambda: (self.store.backup(path), self.status.set(f'Backup saved: {path}')))

    def export(self):
        directory = filedialog.askdirectory(parent=self, title='Choose where to create an export folder')
        if directory:
            target = Path(directory) / datetime.now().strftime('scalp-export-%Y%m%d-%H%M%S-%f')
            self.guard(lambda: (self.store.export(target), self.status.set(f'CSV files saved: {target}')))

    def quit_app(self):
        self.store.close()
        self.destroy()


def main():
    parser = argparse.ArgumentParser(description='Offline shampoo and scalp observation tracker')
    parser.add_argument('--db', type=Path, default=Path.home() / 'ScalpTracker' / 'scalp.sqlite3',
                        help='Database path (default: ~/ScalpTracker/scalp.sqlite3)')
    args = parser.parse_args()
    store = Store(args.db)
    try:
        App(store).mainloop()
    finally:
        store.close()


if __name__ == '__main__':
    main()

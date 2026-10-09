# Scalp Tracker

A desktop application for recording shampoo formulas and scalp observations.
Built with Python, CustomTkinter and SQLite. No account, server or API key.
The interface includes dark/light themes, spaced blue navigation buttons above the
summary cards, auto-sized tables with thick white column separators, centered numeric
columns, mouse-wheel scrolling and taller scrollable forms. Ingredient comparison
differences show a red danger flag for high positive differences and a green check
for high negative differences; neutral differences have no marker.

## Start here

1. Extract the ZIP into a folder.
2. Open a terminal in the extracted `scalp-tracker` folder.
3. With your environment activated, install the GUI dependency:

```sh
python3 -m pip install -r requirements.txt
```

On Windows, use `python -m pip install -r requirements.txt` inside your activated environment.
Installation and optional product-link imports require internet access.
Recording observations, comparisons, backups and exports work offline.

4. Run one of the following commands with Python 3.10 or newer:

```sh
# Windows
py app.py

# macOS / Linux
python3 app.py
```

The app requires a graphical desktop and Tk support. `python -m tkinter` (or
`python3 -m tkinter`) should open a small window. If it reports that tkinter is
missing, add Tk support to your Python installation. On Debian/Ubuntu the OS
package is named `python3-tk`. Python distributions differ in whether they bundle Tk.
CustomTkinter still requires Tkinter. If you previously saw `No module named tkinter`,
install the matching system package first (Ubuntu/Debian: `sudo apt install python3-tk`;
Fedora: `sudo dnf install python3-tkinter`; Arch: `sudo pacman -S tk`). A Python
installation managed by uv, pyenv or Conda may need its own Tk support; the package
must match the interpreter used by your environment.

## Upgrade from the original version

Close the running application. Back up your database, then replace the source files
with this version and install `requirements.txt` inside your existing environment.
Keep your environment folder and database. On first startup, this update adds an
optional source-link field to existing databases; existing records are preserved.
The default data location is unchanged. If you
previously used `--db`, continue passing the same path.

Use the **Dark / Light** menu in the upper-right corner to switch appearance.
The app starts in dark mode; theme choice is not saved between sessions.
The data tables use themed ttk Treeviews alongside CustomTkinter controls to retain
keyboard selection, mouse-wheel scrolling and efficient tabular display. Text fields
support **Ctrl+A** for selecting all text. Native file and confirmation
dialogs follow your operating system's appearance.

The main window starts up to 1500 × 1000 and adapts to the screen. Forms open
in a larger scrollable window with bigger inputs and dropdown text. Rounded
controls and a bundled theme use Segoe UI on Windows and Helvetica on macOS/Linux.
Native dropdown popup borders and window decorations follow the operating system.

## First session

1. In **Products**, click **Add product**. Enter the product/variant and paste the
   exact ingredient list from its label. Avoid copying another country's or an
   older formulation's list without checking it against your bottle.
2. Click **Parse list**, then review the names. Correct the preview to one
   ingredient per line before saving. The original text is retained separately.
3. Add a **Reaction diary** observation with dates, your assessment, symptom
   severity, bump count and bottle type. Notes can record uncertainty about old
   dates, approximate symptom onset, pus, added water, cleaning, baseline symptoms,
   other products or treatments. No product histories are pre-filled.
4. Use **Ingredient patterns** to compare distinct products. Select an ingredient
   to see product names and observation counts. Double-click diary rows to edit
   or read their full notes.
5. Back up the database periodically. CSV export creates a new dated folder
   containing products, ingredients and diary tables, linked by product ID.

You can start by entering your past Labo-H and Australian Bodycare experiences,
using the exact variants and labels you actually used. There is no need to
repeat an exposure to populate the application.

## Import a shampoo from a product link

In **Products**, click **Import from link**, paste a URL to one shampoo, then
click **Read product page**. The app reads the page in the background and opens
an editable review form with the product name, brand, full ingredient text,
parsed ingredient preview and source link. Correct any fields, confirm the
variant/formula against your bottle, then click **Save product**.
Purchase location remains yours to enter; a web listing does not establish
where you bought the bottle. The source link is retained when editing,
backing up or exporting products, and can also be entered manually.

The importer reads Product JSON-LD, labeled ingredient sections/accordions
and tables, including English, Danish and Korean headings. It also reads
Matas's embedded product ingredient-tab data, excluding pH text and label
disclaimers. The supplied Matas Dybderensende Shampoo example yielded its name,
brand and 14 ingredients in a live check. A trailing full stop copied onto a
Matas URL is removed only if that URL returns 404.

Retailer formats vary. The importer requires a clear full list: it refuses
missing, truncated or conflicting lists rather than generating ingredients.
Pages that require JavaScript, login, automated-access challenges, or
image-only ingredient lists may require manual entry. Korean names remain
in Korean; automatic translation and OCR are not included.
Olive Young's current Korean product page loads its ingredient details
separately; full extraction for that page is not yet verified.
Successful extraction still needs review because pages can show another
country's formulation or an older label.

No account or API key is needed. Network requests happen only when you import
a link; HTTPS certificate verification stays enabled. Downloads and redirects
have limits, and failures leave your saved products unchanged. Importing the
same URL again creates a new record after review; it does not merge histories.

## How the comparison works

The Products table shows the brand, product/formula name, number of distinct
reviewed ingredients, negative and positive ingredient counts, and purchase
location. A count such as **2 / 23** means two tagged ingredients among 23 reviewed
ingredients. These counts describe presence, not concentration or ingredient
percentages in the shampoo.

**Recommendation (0–100)** is a personal preference indicator:

`50 + 50 × (positive count − negative count) / total ingredients`

50 is neutral (no tags or balanced tags). More positive ingredients raise the
score; more negative ingredients lower it. For example, 3 positives and
1 negative out of 20 ingredients gives 55. All-positive lists score 100;
all-negative lists score 0. Counts use distinct reviewed ingredients,
and the score updates after formula edits and imports.
Click the **i** button in Products for the explanation. This is not a medical
safety measurement, probability or proof that a shampoo is suitable; it does
not account for concentrations, interactions or diary reactions.

The user-selected **Negative** tags match menthol, peppermint oil, cornmint oil,
tea tree oil (including common botanical INCI oil names), and ingredient names
ending in sulfate/sulphate (singular or plural). This broad sulfate rule includes
mineral sulfates such as magnesium sulfate, not only sulfate surfactants.
Sulfonates and sulfoacetates are not matched by that rule.
The **Positive** tags match glycerin/glycerine/glycerol, colloidal oatmeal,
ceramide labels (such as Ceramide NP, AP, EOP or 3), and zinc pyrithione/pyrithione
zinc. Ordinary oat extracts are not assumed to be colloidal oatmeal.
Matching ignores case and recognizes parenthesized common names in botanical
labels. It does not translate Korean or other ingredient names automatically.
Only the reviewed ingredient list is used; duplicates are counted once.
Tags update automatically after product edits and are shown in the
Ingredient Patterns **Your flag** column. Tags are personal preferences,
not health or safety ratings, and do not alter observation grouping or scores.

Click a **Negative** or **Positive** cell in the **Your flag** column of
Ingredient Patterns or Ingredient Categories to open a scrollable list of
matching saved bottles/formulas. The list shows each product's name, brand,
purchase location and record ID, including products without diary observations.
Unflagged cells do not open a list. These are saved formula records, not
separately identified physical bottles.

| Ingredient Patterns column | Measurement |
|---|---|
| Ingredient | Normalized reviewed ingredient name |
| Your flag | Negative, Positive, or a dash for no matching personal tag |
| Bottles / formulas | Total saved product records containing this ingredient; one per record, including unassessed products |
| Reaction | Products containing the ingredient in the reaction group / all products in that group |
| Tolerated | Products containing the ingredient in the tolerated group / all products in that group |
| Not assessed | Products containing the ingredient without qualifying assessed observations, including reactions only to another selected symptom |
| Reaction Percentage | Reaction-group percentage minus tolerated-group percentage, in percentage points |

**Reaction Percentage** is a renamed comparison column; the calculation is
unchanged. It is not the likelihood that an ingredient causes a reaction.
Click the **i** button beside the symptom selector to see the calculation,
an example, marker thresholds and group definitions. Mixed products are no
longer displayed in a separate table column, but remain excluded from both
comparison percentages and appear in the summary.

Click any table header once for ascending order and again for descending order.
Text sorts alphabetically without case sensitivity; ISO dates sort
chronologically. Numeric columns sort by numeric value, ignoring emoji markers.
Count fractions such as **2 / 23** sort by the numerator (the ingredient or
product count). Missing comparison values remain last in either direction.
An arrow in the active header shows the direction. Sorting is retained when
data refreshes during the session.

The **Ingredient Categories** tab groups reviewed ingredients into Oils,
Fragrance, Anti-fungals, Cleansers, Moisture support, Barrier support, Soothing
ingredients, Preservatives, pH adjusters, Texture / conditioning, Solvents,
and Other / unclassified. Select a category to filter its ingredients and see
a short description of their common role. The table also shows personal flags
and how many product records contain each ingredient.

Categories use a conservative list of common English/INCI names, with rules
for named oils, ceramides and polyquaterniums. An ingredient can have multiple
roles (for example, panthenol appears in moisture support and soothing).
Unknown labels are left unclassified rather than assigned an inferred role.
The categories are composition aids, not safety ratings or recommendations;
an antifungal label alone does not establish concentration or effectiveness.

Physical bottle IDs are not recorded: buying another bottle of the same saved
formula or adding another diary entry does not increase Bottles / formulas.
The diary table shows observation date, product, your explicit assessment,
flakes and itch severity (each 0 = none to 5 = severe), the number of bumps,
and container context (Bottle, Decanted bottle, or Unknown). New observations default to **Bottle**. Existing container values are preserved. Use dates
and notes are available when editing an observation.

The summary cards count saved product records, diary observations, and distinct
normalized ingredients across all products.

You explicitly select **Reaction**, **Tolerated**, or **Unknown / not assessed**.
Symptom scores do not decide the assessment automatically: symptoms may have
been present before using the product. Zero symptoms are never silently treated
as proof of tolerance.

Each product/formula contributes at most once to a group:

| Group | Definition |
|---|---|
| Reaction | At least one reaction observation for the selected symptom, no tolerated observations |
| Tolerated | At least one tolerated observation, no reaction observations of any kind |
| Mixed | Both reaction and tolerated observations; excluded from percentages |
| Unassessed / other | No assessed observations, or reactions only for a different symptom |

For each ingredient, the app shows counts and the difference in percentage points:

`100 × (reaction products containing it / all reaction products − tolerated products containing it / all tolerated products)`

A missing comparison group produces a dash, not a score. Larger positive
differences appear first. For example, presence in 1 of 2 reaction products and
0 of 1 tolerated products gives +50 percentage points. This describes this small
set of records; it is not a probability, allergy diagnosis or confidence score.

Products often share many ingredients. Concentration, exposure, storage, other
products and underlying symptoms can confound comparisons. A high difference
does not isolate an ingredient as a cause. The app makes no claim that a product
or ingredient is safe and does not prescribe a treatment or an exposure experiment.
For now, the app records bottle context but does not adjust comparisons for it.

## Ingredient parsing

- Commas, semicolons and newlines split ingredients outside parentheses.
- Numeric commas such as `1,2-hexanediol` stay intact.
- Case, repeated spaces and Unicode width are normalized.
- A short, explicit alias table groups common water and fragrance label variants.
- Fragrance is a broad label category, not a single chemical identity.
- No fuzzy matching, automatic translation, ingredient safety ratings or external lookup.
- Korean names are preserved and require manual normalization if you want to
  compare them with English names. Check any chemical equivalence yourself.
- Parsing is intentionally conservative and cannot resolve every label format;
  the editable preview is part of the workflow.

Corrections to an existing product change the ingredients used for its historical
observations. For a reformulation, add a new product instead. The GUI warns before
ingredient edits; the original list and notes help you keep provenance.

## Data, privacy and backups

Default database: `ScalpTracker/scalp.sqlite3` in your user home folder. Moving
the source folder or launching from a different directory does not change it.
The optional link importer requests the supplied website and follows its
redirects. Ordinary tracking features stay offline; the app does not use analytics.
The database is an
ordinary unencrypted local file: your operating system, backups or synced home
folder may still expose/copy it. CSV exports and backups contain your observations.

Use **Back up database** to create a consistent SQLite copy. To open a backup
without overwriting the original, close the app and run:

```sh
python3 app.py --db "/path/to/backup.sqlite3"
```

On Windows use `py` instead of `python3` if appropriate. The selected file becomes
the live writable database. To restore the default database, close the app,
keep a copy of the current database, and replace it with your backup.

CSV is for inspection/export, not full-fidelity restore; import is not implemented.
Potential spreadsheet formulas in text cells are prefixed with an apostrophe
for safer viewing. Use SQLite backups when you need the exact original data.

## Understand and extend the code

| File | Responsibility |
|---|---|
| `theme.json` | Bundled colors, font defaults and rounded control styling |
| `app.py` | CustomTkinter screens, dialogs, themes, events and input handling |
| `requirements.txt` | Pinned GUI and web-import dependencies |
| `product_import.py` | Product-page fetching and reviewed ingredient extraction |
| `core.py` | SQLite schema, validation, parsing, comparisons, backup and export |
| `tests/test_core.py` | Regression tests using temporary databases |

The GUI calls `Store` methods, and `Store` never imports the GUI. This makes the
data logic testable without opening a window. SQL values use placeholders rather
than string interpolation. Foreign keys keep entries linked to valid products.
Writes use transactions. Product deletion also deletes its observations, after
confirmation in the GUI.

Run tests from the project directory:

```sh
python3 -m unittest discover -s tests -v
```

Suggested learning steps:

1. Read `parse_ingredients`, add one carefully checked alias and a regression test.
2. Trace **Save observation** from `entry_dialog` to `Store.save_entry`.
3. Add a bottle identifier so multiple decanted bottles can be distinguished.
4. Add a symptom timeline based on diary observations.
5. Before changing the database schema, introduce versioned migrations and backup tests.

## Version 1.1 repair: limits and verification

This is source code, not a packaged `.exe` or macOS application. It supports
product and diary CRUD, reviewed ingredient parsing, symptom-specific descriptive
comparisons, CSV export and SQLite backups. No photos, barcode lookup, automatic
translation, CSV import, encryption, statistical causal model or automatic backups.

Backend tests cover ingredient parsing, grouping, denominator calculations,
symptom filtering, validation, edits/deletion, persistence, Unicode export and
backup recovery. All seven backend tests and the GUI smoke test passed. The original
startup failure was reproduced under Xvfb; the repaired window was opened and visually
inspected. The GUI test covers navigation, themes, forms, wide tables and resizing.
See `FIXES.md` for the repair details. You can explore using a disposable database:

```sh
python3 app.py --db ./practice.sqlite3
```

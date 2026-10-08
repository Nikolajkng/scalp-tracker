# Startup and layout fixes

Your blue colors, larger navigation labels, summary cards below the content,
centered numeric columns, select-all shortcuts and difference markers are retained.
The database code and schema are unchanged.

## Why startup failed

The edited startup code called `pack_configure(padx=8)` on children of
`book._segmented_button`. CustomTkinter lays those children out with `grid`.
A parent cannot mix packed and gridded children; Tk raises a layout error.
Also, CTkTabview reserves a fixed-height navigation area, so enlarging its
private segmented button can cause clipping even after removing the pack call.

The fix uses a standalone public `CTkSegmentedButton` above stacked content
frames. Buttons switch pages with `tkraise()`. This supports your large labels
without modifying CustomTkinter's private layout.

## Other repairs

- Reserved space for the footer so backup/export buttons remain visible.
- Horizontal scrollbars make wide tables accessible. Auto-sized columns are
  capped at 480 pixels and column dividers follow horizontal scrolling.
- Filtering ingredient comparisons now recalculates column widths.
- Removed additional mouse-wheel handlers, which overlapped the widgets'
  built-in scrolling and could cause double scrolling.
- Dialog height adapts to the screen and keeps the scrollable form.
- Unexpected Tk errors retain their traceback instead of always reporting
  a missing graphical desktop.
- The ZIP contains one `scalp-tracker` folder instead of two nested copies.

## Run

Close the previous app. Extract this project; preserve your existing environment.
From the folder containing `app.py`, with your environment activated:

```sh
python3 -m pip install -r requirements.txt
python3 app.py
```

The default database is still `~/ScalpTracker/scalp.sqlite3`. If you previously
used `--db`, pass the same path. No database is included or overwritten by this ZIP.

## Checks

```sh
python3 -m unittest discover -s tests -v
```

The GUI smoke test requires a graphical desktop; it is skipped on headless Linux.
It covers startup, both themes, all pages, both forms, wide data and resizing.
The seven original backend tests also remain included.

Validation: reproduced the original pack/grid crash, then passed all eight tests
under a virtual X display and inspected the repaired main window.

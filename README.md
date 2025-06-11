# FileRename Utility

This is a small GUI/CLI tool that suggests new filenames for your files.

The default mode uses a simple slug generation from the file's content, but
optionally a Gemma model can be used if available. The application ensures that
suggested names are unique. When a duplicate is detected, it retries up to three
times and, if necessary, appends a numeric suffix like `-1` to the filename. A
suffix is only added when a duplicate would otherwise occur.

In the GUI you can select files, review their suggested names, regenerate a
suggestion for any file and choose which files to actually rename.

## Running

```bash
python main.py            # launch the GUI
python main.py --cli file1.txt file2.txt   # CLI suggestions
python main.py --cli --rename file1.txt    # CLI rename using suggestions
```

## Tests

```
pytest
```

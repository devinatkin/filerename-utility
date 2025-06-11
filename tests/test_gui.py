import os
import tkinter as tk
from unittest import mock
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


def test_select_files_adds_rows(tmp_path):
    # create dummy files
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("hello")
    f2.write_text("world")

    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        pytest.skip("Tk not available")
    app = main.FileRenamerUI(root)

    with mock.patch('main.filedialog.askopenfilenames', return_value=[str(f1), str(f2)]), \
         mock.patch('main.suggest_new_filename', return_value={'suggested_filename': 'x'}), \
         mock.patch('threading.Thread') as thread_mock:
        # make background thread run immediately
        thread_mock.return_value = mock.Mock(start=lambda: app.process_files())
        app.select_files()
        assert set(app.tree.get_children()) == {str(f1), str(f2)}

    root.destroy()


def test_unique_suggestion_skips_suffix_when_same_name(tmp_path):
    file_path = tmp_path / "original.txt"
    file_path.write_text("hello world")

    with mock.patch('main.suggest_new_filename', return_value={'suggested_filename': 'original'}):
        result = main.unique_suggestion(str(file_path), set())
    assert result == 'original'


def test_regenerate_and_rename(tmp_path):
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        pytest.skip("Tk not available")

    f1 = tmp_path / "a.txt"
    f1.write_text("hello")
    app = main.FileRenamerUI(root)
    app.files = [str(f1)]
    app.file_data = {str(f1): 'name'}
    app.rename_vars = {str(f1): tk.IntVar(value=1)}

    with mock.patch('main.suggest_new_filename', return_value={'suggested_filename': 'newname'}):
        app.regenerate_filename(str(f1))
    assert app.file_data[str(f1)] == 'newname'

    app.rename_files()
    assert (tmp_path / 'newname.txt').exists()
    root.destroy()

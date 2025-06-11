"""Simple filename suggestion utilities.

The original implementation relied on the HuggingFace ``transformers``
library to generate suggestions with a large language model.  The
environment used in Codex does not provide this dependency and
attempting to load the model causes the application to fail on start.

To keep the GUI functional and self‑contained we replace the heavy
dependency with a lightweight heuristic that generates a filename based
on the contents of the file.  This keeps the public API unchanged while
allowing the rest of the program to run without additional downloads.
"""

import os
import json
import re
import argparse
from functools import lru_cache

try:
    from PyPDF2 import PdfReader
except Exception:  # Package not installed
    PdfReader = None

def extract_pdf_text(filepath, max_pages=5):
    """Extract text from the first ``max_pages`` of a PDF.

    If ``PyPDF2`` is not available, this falls back to reading the raw
    bytes and returning a best-effort ASCII decode.
    """
    if PdfReader is None:
        try:
            with open(filepath, "rb") as f:
                data = f.read(4096)
            return data.decode("ascii", errors="ignore")
        except Exception:
            return ""

    text = ""
    try:
        reader = PdfReader(filepath)
        for page in reader.pages[:max_pages]:
            text += page.extract_text() or ""
    except Exception:
        text = ""
    return text.strip()

def slugify(text, max_words=6):
    """Create a simple slug from the provided text."""
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return "-".join(words[:max_words]) or "file"

def extract_json_from_response(response):
    """Extract the first valid JSON object found in ``response``."""
    matches = re.findall(r"\{.*?\}", response, re.DOTALL)
    for match in matches:
        try:
            obj = json.loads(match)
            if (
                isinstance(obj, dict)
                and obj.get("suggested_filename")
                and obj["suggested_filename"] != "<filename>"
            ):
                return obj
        except Exception:
            continue
    return {"suggested_filename": None}

@lru_cache(maxsize=1)
def _load_gemma_model():
    """Lazily load the Gemma model and tokenizer."""
    from transformers import AutoTokenizer, Gemma3ForCausalLM

    model_id = "google/gemma-3-1b-it"
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = Gemma3ForCausalLM.from_pretrained(model_id, device_map="auto").eval()
    return tokenizer, model

def _suggest_with_gemma(filepath, count=1):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        content = extract_pdf_text(filepath)
    else:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(2048)

    prompt = (
        "You are an AI assistant that suggests clear, descriptive filenames for files based on their content. "
        "Given the file content below, suggest a new filename (without extension) that summarizes the main topic or purpose. "
        "Respond ONLY in JSON format as {\"suggested_filename\": \"<filename>\"}.\n\n"
        f"File content (truncated):\n{content[:1500]}"
        f"\n\nCurrent filename: {os.path.basename(filepath)}\n"
        "Rules:\n"
        "- Do NOT include the file extension in your suggestion.\n"
        "- Use only lowercase letters, numbers, hyphens, or underscores.\n"
        "- Make the filename concise and relevant to the content.\n"
        "- Do NOT use generic names like 'document' or 'file'.\n"
        "- Do NOT use <filename> as a placeholder. Suggest a real filename.\n"
    )

    tokenizer, model = _load_gemma_model()

    results = []
    for _ in range(count):
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048).to(model.device)
        outputs = model.generate(**inputs, max_new_tokens=100)
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        result = extract_json_from_response(response)
        results.append(result)
    return results if count > 1 else results[0]

def suggest_new_filename(filepath, count=1, method="slugify"):
    """Generate a filename suggestion for ``filepath`` using the specified ``method``."""
    ext = os.path.splitext(filepath)[1].lower()
    if method == "gemma":
        return _suggest_with_gemma(filepath, count)

    # default slugify approach
    if ext == ".pdf":
        content = extract_pdf_text(filepath)
    else:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(2048)
        except Exception:
            content = ""

    slug = slugify(content)
    result = {"suggested_filename": slug}
    if count > 1:
        return [result for _ in range(count)]
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Suggest new file names")
    parser.add_argument("files", nargs="+", help="Files to analyse")
    parser.add_argument("-m", "--method", choices=["slugify", "gemma"], default="slugify",
                        help="Suggestion method")
    parser.add_argument("-c", "--count", type=int, default=1, help="Number of suggestions")
    parser.add_argument("--rename", action="store_true", help="Rename files using first suggestion")
    args = parser.parse_args()

    for path in args.files:
        suggestion = suggest_new_filename(path, count=args.count, method=args.method)
        print(json.dumps({"file": path, "suggestion": suggestion}, indent=2))
        if args.rename:
            new_base = suggestion[0]["suggested_filename"] if isinstance(suggestion, list) else suggestion["suggested_filename"]
            ext = os.path.splitext(path)[1]
            new_path = os.path.join(os.path.dirname(path), new_base + ext)
            try:
                os.rename(path, new_path)
            except Exception as exc:
                print(f"Failed to rename {path}: {exc}")

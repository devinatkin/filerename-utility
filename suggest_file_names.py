import os
import json
from transformers import AutoTokenizer, Gemma3ForCausalLM
from PyPDF2 import PdfReader

# Load model and tokenizer once
model_id = "google/gemma-3-1b-it"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = Gemma3ForCausalLM.from_pretrained(model_id, device_map="auto").eval()

def extract_pdf_text(filepath, max_pages=5):
    text = ""
    try:
        reader = PdfReader(filepath)
        for page in reader.pages[:max_pages]:
            text += page.extract_text() or ""
    except Exception:
        text = ""
    return text.strip()

def extract_json_from_response(response):
    """
    Extract the first valid JSON object found in the response string.
    """
    import re

    # Find all JSON-like objects in the response
    matches = re.findall(r'\{.*?\}', response, re.DOTALL)
    for match in matches:
        try:
            obj = json.loads(match)
            # Ensure the key exists and is not a placeholder
            if (
                isinstance(obj, dict)
                and "suggested_filename" in obj
                and obj["suggested_filename"]
                and obj["suggested_filename"] != "<filename>"
            ):
                return obj
        except Exception:
            continue
    return {"suggested_filename": None}

def suggest_new_filename(filepath, count=1):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        content = extract_pdf_text(filepath)
    else:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(2048)  # Read first 2KB for context

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

    results = []
    for _ in range(count):
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048).to(model.device)
        outputs = model.generate(**inputs, max_new_tokens=100)
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        result = extract_json_from_response(response)
        if result["suggested_filename"] is None:
            print("Failed to parse JSON response:", response)
        results.append(result)
    return results if count > 1 else results[0]

if __name__ == "__main__":
    # Example usage:
    print(suggest_new_filename("test.pdf", 3))

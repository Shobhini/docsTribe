import os


def read_file(file_path: str, filename: str) -> str:
    """
    Read a file and return its text content.
    Supports: .txt, .pdf, .png, .jpg, .jpeg
    """
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    elif ext == ".pdf":
        from pdf2image import convert_from_path
        import pytesseract
        pages = convert_from_path(file_path)
        text_parts = []
        for page in pages:
            text_parts.append(pytesseract.image_to_string(page))
            page.close()
        return "\n".join(text_parts)

    elif ext in (".png", ".jpg", ".jpeg"):
        from PIL import Image
        import pytesseract
        with Image.open(file_path) as image:
            return pytesseract.image_to_string(image)

    else:
        raise ValueError(f"Unsupported file type: {ext}. Allowed: .txt, .pdf, .png, .jpg, .jpeg")

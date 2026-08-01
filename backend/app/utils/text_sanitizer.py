import re

def sanitize_text(text: str) -> str:
    """
    Removes NULL bytes and invalid control characters (except newline, carriage return and tab).
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    # Remove NULL bytes
    text = text.replace("\x00", "")
    # Remove invalid control characters (0-31 and 127) except tab (9), newline (10), and carriage return (13)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    return text

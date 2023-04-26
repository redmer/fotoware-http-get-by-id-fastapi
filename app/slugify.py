import re


def slugify(s: str, /):
    """Render a slug from a string"""
    s = s.lower().strip()
    s = re.sub(r"[^\s\w-]", "", s)  # del non [whitespace, letterlikes, dashes]
    s = re.sub(r"[\s_-]+", "-", s)  # replace all 2+ of whitespace, underscore, dashes
    s = re.sub(r"^-+|-+$", "", s)  # del dashes at begin or end of string
    return s

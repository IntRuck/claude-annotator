"""Small text helpers shared by features."""


def one_line(text: str | None) -> str:
    """Collapse all whitespace (including newlines) to single spaces and trim."""
    return " ".join((text or "").split())


def clean_class_name(text: str | None) -> str:
    """A YOLO class name: one word, spaces become underscores ("tuna 400g" -> "tuna_400g")."""
    return one_line(text).replace(" ", "_")

import re


_HOUSEHOLD_STAPLE_NAMES = {
    "water",
    "tap water",
    "filtered water",
    "cold water",
    "warm water",
    "hot water",
    "boiling water",
    "ice water",
    "ice",
    "salt",
    "table salt",
    "sea salt",
    "kosher salt",
    "black pepper",
    "ground black pepper",
    "freshly ground black pepper",
}


def _normalize_ingredient_name(value: str) -> str:
    lowered = (value or "").strip().lower()
    lowered = re.sub(r"\([^)]*\)", " ", lowered)
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def is_household_staple(value: str) -> bool:
    """
    Ingredients everyone is expected to have should not become pantry or shopping-list requirements.
    """
    normalized = _normalize_ingredient_name(value)
    if normalized in _HOUSEHOLD_STAPLE_NAMES:
        return True
    if normalized.endswith(" water") and normalized.split()[-2:] != ["coconut", "water"]:
        return True
    return False


def filter_household_staples(ingredients: list[str]) -> list[str]:
    return [item for item in ingredients if not is_household_staple(item)]

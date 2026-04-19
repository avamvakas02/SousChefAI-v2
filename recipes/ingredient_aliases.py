import re


_CANONICAL_ALIASES: dict[str, tuple[str, ...]] = {
    # Dairy / fats
    "butter": (
        "butter",
        "salted butter",
        "unsalted butter",
        "clarified butter",
        "brown butter",
        "cultured butter",
        "european butter",
        "whipped butter",
        "ghee",
    ),
    "milk": (
        "milk",
        "dairy milk",
        "whole milk",
        "skim milk",
        "semi skim milk",
        "semi skimmed milk",
        "2 milk",
        "1 milk",
        "evaporated milk",
        "condensed milk",
    ),
    "cream": (
        "cream",
        "heavy cream",
        "double cream",
        "single cream",
        "whipping cream",
    ),
    "yogurt": ("yogurt", "yoghurt", "greek yogurt", "greek yoghurt"),
    "cheese": (
        "cheese",
        "cheddar",
        "mozzarella",
        "parmesan",
        "feta",
        "ricotta",
        "cream cheese",
        "goat cheese",
        "cottage cheese",
    ),
    # Eggs
    "egg": ("egg", "eggs", "egg white", "egg yolk"),
    # Oils
    "olive oil": ("olive oil", "extra virgin olive oil", "evoo"),
    "vegetable oil": ("vegetable oil", "canola oil", "sunflower oil", "rapeseed oil"),
    "coconut oil": ("coconut oil",),
    "sesame oil": ("sesame oil", "toasted sesame oil"),
    # Sweeteners / baking
    "sugar": ("sugar", "white sugar", "caster sugar", "granulated sugar"),
    "brown sugar": ("brown sugar", "light brown sugar", "dark brown sugar", "demerara"),
    "powdered sugar": ("powdered sugar", "icing sugar", "confectioners sugar"),
    "flour": ("flour", "all purpose flour", "plain flour"),
    "bread flour": ("bread flour",),
    "whole wheat flour": ("whole wheat flour", "wholemeal flour"),
    "cornstarch": ("cornstarch", "corn flour", "cornflour"),
    # Grains / starches
    "rice": ("rice", "white rice", "long grain rice", "jasmine rice", "basmati rice"),
    "brown rice": ("brown rice",),
    "pasta": ("pasta", "spaghetti", "penne", "fusilli", "linguine", "macaroni"),
    "noodles": ("noodles", "egg noodles", "rice noodles"),
    "bread": ("bread", "white bread", "whole wheat bread", "sourdough"),
    "oats": ("oats", "rolled oats", "quick oats"),
    # Legumes / nuts
    "beans": ("beans", "kidney beans", "black beans", "white beans", "cannellini beans"),
    "chickpeas": ("chickpeas", "garbanzo beans"),
    "lentils": ("lentils", "red lentils", "green lentils"),
    "peanuts": ("peanuts", "groundnuts"),
    "almonds": ("almond", "almonds"),
    "cashews": ("cashew", "cashews"),
    "walnuts": ("walnut", "walnuts"),
    # Alliums / aromatics
    "onion": ("onion", "onions", "red onion", "white onion", "yellow onion"),
    "garlic": ("garlic", "garlic clove", "garlic cloves"),
    "ginger": ("ginger", "fresh ginger", "ginger root"),
    "scallion": ("scallion", "scallions", "spring onion", "spring onions", "green onion"),
    # Produce
    "tomato": ("tomato", "tomatoes", "plum tomato", "cherry tomato"),
    "potato": ("potato", "potatoes", "russet potato", "red potato"),
    "carrot": ("carrot", "carrots"),
    "bell pepper": ("bell pepper", "capsicum", "red pepper", "green pepper", "yellow pepper"),
    "chili pepper": ("chili", "chilli", "chile", "hot pepper"),
    "mushroom": ("mushroom", "mushrooms", "button mushroom", "shiitake"),
    "spinach": ("spinach", "baby spinach"),
    "lettuce": ("lettuce", "romaine", "iceberg lettuce"),
    "cabbage": ("cabbage", "red cabbage", "green cabbage"),
    "broccoli": ("broccoli",),
    "cauliflower": ("cauliflower",),
    "zucchini": ("zucchini", "courgette"),
    "eggplant": ("eggplant", "aubergine"),
    "cucumber": ("cucumber",),
    "celery": ("celery",),
    "apple": ("apple", "apples"),
    "banana": ("banana", "bananas"),
    "lemon": ("lemon", "lemons"),
    "lime": ("lime", "limes"),
    "orange": ("orange", "oranges"),
    "avocado": ("avocado", "avocados"),
    # Proteins / seafood
    "chicken": ("chicken", "chicken breast", "chicken thighs", "chicken thigh"),
    "beef": ("beef", "beef mince", "ground beef", "beef steak", "minced beef"),
    "pork": ("pork", "pork chop", "pork belly", "ground pork", "minced pork"),
    "lamb": ("lamb", "lamb chops"),
    "turkey": ("turkey", "ground turkey"),
    "bacon": ("bacon",),
    "sausage": ("sausage", "sausages"),
    "ham": ("ham",),
    "tofu": ("tofu", "firm tofu", "silken tofu"),
    "fish": ("fish", "white fish"),
    "salmon": ("salmon",),
    "tuna": ("tuna",),
    "cod": ("cod",),
    "shrimp": ("shrimp", "prawn", "prawns"),
    "crab": ("crab",),
    "squid": ("squid", "calamari"),
    "mussels": ("mussel", "mussels"),
    # Condiments / sauces
    "soy sauce": ("soy sauce", "light soy sauce", "dark soy sauce"),
    "vinegar": ("vinegar", "white vinegar", "distilled vinegar"),
    "apple cider vinegar": ("apple cider vinegar",),
    "balsamic vinegar": ("balsamic vinegar",),
    "ketchup": ("ketchup", "tomato ketchup"),
    "mustard": ("mustard", "dijon mustard"),
    "mayonnaise": ("mayonnaise", "mayo"),
    "hot sauce": ("hot sauce", "tabasco", "chili sauce"),
    "tomato paste": ("tomato paste",),
    "tomato sauce": ("tomato sauce", "passata"),
    "broth": ("broth", "stock", "chicken stock", "vegetable stock", "beef stock"),
    # Herbs / spices
    "salt": ("salt", "sea salt", "kosher salt"),
    "black pepper": ("black pepper", "pepper"),
    "paprika": ("paprika", "smoked paprika"),
    "cumin": ("cumin", "ground cumin"),
    "turmeric": ("turmeric",),
    "coriander": ("coriander", "ground coriander"),
    "oregano": ("oregano",),
    "thyme": ("thyme",),
    "basil": ("basil",),
    "parsley": ("parsley",),
    "cilantro": ("cilantro", "coriander leaves"),
    "cinnamon": ("cinnamon",),
    "nutmeg": ("nutmeg",),
    "bay leaf": ("bay leaf", "bay leaves"),
    "chili flakes": ("chili flakes", "red pepper flakes"),
}

_DESCRIPTOR_WORDS = {
    "fresh",
    "organic",
    "lowfat",
    "low fat",
    "fat free",
    "reduced fat",
    "full fat",
    "extra virgin",
    "virgin",
    "raw",
    "plain",
    "light",
    "large",
    "small",
    "medium",
    "extra",
    "lean",
    "boneless",
    "skinless",
    "frozen",
    "dried",
    "chopped",
    "diced",
    "sliced",
    "minced",
    "crushed",
    "ground",
    "powder",
    "powdered",
    "whole",
    "halved",
    "shredded",
    "grated",
    "toasted",
    "unsweetened",
    "sweetened",
}

_UNIT_WORDS = {
    "g",
    "kg",
    "ml",
    "l",
    "lb",
    "lbs",
    "oz",
    "cup",
    "cups",
    "tbsp",
    "tsp",
    "tablespoon",
    "tablespoons",
    "teaspoon",
    "teaspoons",
    "clove",
    "cloves",
    "slice",
    "slices",
    "piece",
    "pieces",
    "can",
    "cans",
    "pack",
    "packs",
    "bunch",
    "pinch",
    "dash",
}

_ALIAS_BY_PHRASE: dict[str, str] = {
    alias: canonical for canonical, aliases in _CANONICAL_ALIASES.items() for alias in aliases
}
_SORTED_ALIASES = sorted(_ALIAS_BY_PHRASE.keys(), key=lambda a: (-len(a), a))


def _normalize_text(value: str) -> str:
    s = (value or "").strip().lower()
    # Drop parenthetical notes and punctuation noise.
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _drop_leading_quantities(text: str) -> str:
    s = text
    s = re.sub(r"^\d+([./]\d+)?\s*", "", s)
    s = re.sub(r"^(a|an)\s+", "", s)
    return s.strip()


def _clean_tokens(text: str) -> str:
    tokens = [t for t in text.split() if t]
    cleaned = [
        t
        for t in tokens
        if t not in _DESCRIPTOR_WORDS and t not in _UNIT_WORDS and not t.isdigit()
    ]
    return " ".join(cleaned).strip()


def canonicalize_ingredient_name(value: str) -> str:
    """
    Return a canonical pantry-matching name.
    Keeps existing ingredient text when no alias family is matched.
    """
    text = _normalize_text(value)
    if not text:
        return ""
    text = _drop_leading_quantities(text)
    text = _clean_tokens(text)
    if not text:
        return ""

    for alias in _SORTED_ALIASES:
        if re.search(rf"\b{re.escape(alias)}\b", text):
            return _ALIAS_BY_PHRASE[alias]

    # Try a lighter cleanup for cases where descriptors were meaningful.
    fallback = _drop_leading_quantities(_normalize_text(value))
    for alias in _SORTED_ALIASES:
        if re.search(rf"\b{re.escape(alias)}\b", fallback):
            return _ALIAS_BY_PHRASE[alias]

    return text

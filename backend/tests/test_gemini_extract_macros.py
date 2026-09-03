from app.gemini_extract import _draft_from_parsed


def test_gemini_stated_macros_only_when_present():
    draft, stated = _draft_from_parsed(
        {
            "title": "High protein pasta",
            "ingredients": ["200g pasta", "150g chicken"],
            "steps": ["Boil pasta", "Cook chicken"],
            "servings": 2,
            "stated_calories": 520,
            "stated_protein_g": 45,
            "stated_carbs_g": 40,
            "stated_fat_g": 12,
            "stated_fiber_g": None,
            "dietary_flags": ["high-protein"],
        }
    )
    assert draft.title == "High protein pasta"
    assert draft.ingredients == ["200g pasta", "150g chicken"]
    assert stated is not None
    assert stated.per_serving.calories == 520
    assert stated.per_serving.protein_g == 45
    assert stated.source and "stated" in stated.source.lower()


def test_gemini_no_invented_macros_when_null():
    draft, stated = _draft_from_parsed(
        {
            "title": "Soup",
            "ingredients": ["broth"],
            "steps": ["simmer"],
            "stated_calories": None,
            "stated_protein_g": None,
            "stated_carbs_g": None,
            "stated_fat_g": None,
        }
    )
    assert draft.title == "Soup"
    assert stated is None

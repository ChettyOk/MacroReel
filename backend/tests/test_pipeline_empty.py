from app.pipeline import _is_empty_recipe_draft
from app.schemas import RecipeBase


def test_empty_parse_title_is_rejected():
    assert _is_empty_recipe_draft(RecipeBase(title="Could not parse recipe", ingredients=[], steps=[]))


def test_draft_with_ingredients_is_kept():
    assert not _is_empty_recipe_draft(
        RecipeBase(title="Could not parse recipe", ingredients=["1 egg"], steps=[])
    )


def test_real_title_without_body_is_rejected():
    assert _is_empty_recipe_draft(RecipeBase(title="Imported recipe", ingredients=[], steps=[]))

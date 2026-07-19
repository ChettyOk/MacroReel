import pytest
from pydantic import ValidationError

from app.schemas import ForgotPasswordReset, UserRegister


def _register(**overrides):
    base = {
        "email": "user@example.com",
        "password": "SecurePass1",
        "security_question": "Favorite color?",
        "security_answer": "blue",
    }
    base.update(overrides)
    return UserRegister(**base)


def test_register_accepts_letter_and_digit_password():
    user = _register(password="SecurePass1")
    assert user.password == "SecurePass1"


@pytest.mark.parametrize("password", ["short1A", "allletters", "12345678", "NoDigitHere"])
def test_register_rejects_weak_password(password: str):
    with pytest.raises(ValidationError):
        _register(password=password)


def test_reset_rejects_weak_password():
    with pytest.raises(ValidationError):
        ForgotPasswordReset(
            email="user@example.com",
            security_answer="blue",
            new_password="password",
        )

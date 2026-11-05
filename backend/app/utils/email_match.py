"""The one rule for deciding whether two email addresses are the same (PD-002, B39).

Sign-in, the access list, ACCESS_BOOTSTRAP_EMAILS and manage_access.py all compare
addresses through ``normalise_email``. Two addresses match only if they're the same
letter for letter, ignoring capital letters and spaces at either end.

No Unicode case-folding or compatibility normalisation (NFKC and friends): those turn
some look-alike characters into ASCII (the Kelvin sign U+212A lower-cases to "k",
fullwidth letters fold to plain ones), which would let a different address pass as a
listed one. An address with any non-ASCII character can't be compared safely, so it's
refused rather than guessed at.
"""
from typing import Optional

# ASCII whitespace only; str.strip() with no argument also removes Unicode spaces.
_ASCII_SPACE = " \t\r\n\f\v"


class UnsafeEmailError(ValueError):
    """The address has characters that can't be compared safely."""


def normalise_email(email: Optional[str]) -> str:
    """The comparison key for an address: trimmed and lower-cased, ASCII only.

    Returns "" for a missing or blank address. Raises ``UnsafeEmailError`` if any
    character outside ASCII remains, so callers refuse it with a clear message.
    """
    value = (email or "").strip(_ASCII_SPACE)
    if not value.isascii():
        raise UnsafeEmailError("email contains non-ASCII characters")
    # Safe now: on an ASCII string, lower() only changes A-Z.
    return value.lower()


def is_safe_email(email: Optional[str]) -> bool:
    try:
        normalise_email(email)
    except UnsafeEmailError:
        return False
    return True

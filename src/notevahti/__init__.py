"""NoteVahti — transparent, local-first extraction-validation toolkit for clinical registry data.

NoteVahti validates values that *something else* extracted; it is never the source of truth.
The validation core is deterministic, model-free, and offline. See SKILL.md and docs/design/.
"""

__version__ = "0.1.0.dev0"

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # give type checkers the real symbol without importing eagerly at runtime
    from .validate import validate_field as validate_field


def __getattr__(name: str) -> object:
    # Lazy re-export so that importing the package does not import submodules eagerly
    # (keeps `import notevahti` cheap and avoids import cycles with `validate`).
    if name == "validate_field":
        from .validate import validate_field

        return validate_field
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["__version__", "validate_field"]

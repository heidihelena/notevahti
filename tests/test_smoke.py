"""Step 0 smoke test: the package imports and exposes a version."""

import notevahti


def test_version_present():
    assert isinstance(notevahti.__version__, str)
    assert notevahti.__version__


def test_package_docstring_states_it_validates():
    # The package's purpose statement is part of the contract.
    assert "validat" in (notevahti.__doc__ or "").lower()

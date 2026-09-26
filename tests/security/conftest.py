"""The security suite reuses the integration and validation fixtures."""

from tests.integration.conftest import complaint_id  # noqa: F401
from tests.unit.test_validation_checks import rules, vocab  # noqa: F401

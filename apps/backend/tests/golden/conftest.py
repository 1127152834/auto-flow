"""Explicit fixture registration; a sibling integration module is not a plugin."""

from tests.integration.test_workflow_real_cloakbrowser import real_cloak_page

__all__ = ["real_cloak_page"]

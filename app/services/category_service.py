"""
Category vocabulary management service (see SP-041).

Mirrors AuthService's shape: takes a raw database file path, builds its own
SqliteCategoryDatabase, and exposes (success, error) tuples for mutations so
routes can flash the error message straight through, same as
AuthService.add_user/set_admin.

A category is never truly deleted - only hidden/unhidden. Hiding only
affects what's offered for *future* assignment (see get_visible_category_names);
anything already using a hidden category is completely unaffected, since
receipt_items/transactions reference categories.id (SP-044), not a
duplicated name string.
"""

from typing import Dict, List, Optional, Tuple

from ..database.sqlite_category_db import SqliteCategoryDatabase

# The universal fallback category - protected from being hidden, since a lot
# of code (LLM extraction, edit-form validation) defaults an unrecognized
# category to this name and assumes it's always a legitimate choice.
_PROTECTED_CATEGORY_NAME = 'Other'


class CategoryService:
    """Manages the category vocabulary: add, rename, hide/unhide."""

    def __init__(self, database_path: str):
        self._storage = SqliteCategoryDatabase(database_path)

    def get_all_categories(self) -> List[Dict]:
        """Every category (visible and hidden), for the admin page."""
        return self._storage.get_all_categories()

    def get_visible_category_names(self) -> List[str]:
        """Names of non-hidden categories - what's offered for new assignment
        (LLM prompts, edit-form dropdowns)."""
        return [c['name'] for c in self._storage.get_all_categories() if not c['hidden']]

    def add_category(self, name: str) -> Tuple[bool, Optional[str]]:
        """Add a new category. Rejects a blank name or one that already exists."""
        name = name.strip()
        if not name:
            return False, 'Please enter a category name.'
        if self._storage.get_category_by_name(name) is not None:
            return False, 'That category already exists.'

        self._storage.add_category(name)
        return True, None

    def rename_category(self, category_id: int, new_name: str) -> Tuple[bool, Optional[str]]:
        """Rename an existing category. Every item/transaction already using
        it shows the new name immediately (it references the id, not this
        name) - no cascade needed."""
        new_name = new_name.strip()
        if not new_name:
            return False, 'Please enter a category name.'

        category = self._storage.get_category_by_id(category_id)
        if category is None:
            return False, 'Category not found.'

        existing = self._storage.get_category_by_name(new_name)
        if existing is not None and existing['id'] != category_id:
            return False, 'That category already exists.'

        self._storage.rename_category(category_id, new_name)
        return True, None

    def toggle_hidden(self, category_id: int) -> Tuple[bool, Optional[str]]:
        """Flip a category's hidden flag. The protected 'Other' category can
        never be hidden - it's the universal fallback everything else
        depends on (mirrors the last-admin safeguard in AuthService)."""
        category = self._storage.get_category_by_id(category_id)
        if category is None:
            return False, 'Category not found.'

        new_hidden = not category['hidden']
        if new_hidden and category['name'] == _PROTECTED_CATEGORY_NAME:
            return False, f"The {_PROTECTED_CATEGORY_NAME} category can't be hidden."

        self._storage.set_hidden(category_id, new_hidden)
        return True, None

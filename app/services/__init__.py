"""
Services package initialization.

Services contain business logic - the "what" and "how" of processing data.
They are independent of Flask (web framework) and database implementation.

This separation allows us to:
- Test business logic without running the web server
- Reuse logic in different contexts (web, CLI, API, etc.)
- Keep code organized and maintainable
"""

from .llm_service import LLMService
from .receipt_service import ReceiptService

__all__ = ['LLMService', 'ReceiptService']

"""KOREA-LIFE — multilingual personal assistant for foreign residents in South Korea.

This package holds the application's core logic, kept separate from the
Streamlit UI so it can be imported and unit-tested on its own:

- config      : paths and environment configuration
- database    : SQLite persistence (profiles + reminders/tasks)
- knowledge   : retrieval over the curated official-source knowledge base
- ai          : Claude API client with a deterministic offline fallback
- reminders   : the Life Manager reminder engine (status, recurrence, offsets)
- i18n        : small UI translation dictionary
"""

__version__ = "1.0.0"
__app_name__ = "KOREA-LIFE"

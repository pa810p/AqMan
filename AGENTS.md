# Coding guidelines

- Use English names for variables, functions, classes, and files.
- Keep comments minimal and concise. Add comments only when the intent is not obvious from the code.
- Do not use empty try-catch blocks or silently ignore exceptions.
- Use constants or defines instead of magic numbers.
- Use the existing logging system for important events and choose appropriate log levels.
- Do not implement production code that is required or valid only for tests

# Problem solving

- Always provide a checked and verified solution.
- I you are not 100% sure the answer, say shortly: DONT KNOW 
- Do not implement features or changes that were not explicitly requested.
- Prefer minimal changes over unnecessary refactoring.
- Before modifying code, understand the existing architecture and constraints.

# Environment using
- use local python environment
- for testing use timeout 10s xvfb-run python -m pytest


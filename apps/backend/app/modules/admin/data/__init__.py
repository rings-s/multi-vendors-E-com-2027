"""Generic data administration (in the spirit of the Django admin).

Every table in ``SQLModel.metadata`` is registered automatically; ``registry`` holds the
per-table overrides (display field, list columns, search, filters, read-only and hidden
columns, choices, what can be added, changed or deleted).
"""

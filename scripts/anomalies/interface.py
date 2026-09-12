"""Phase 6 event contracts."""

DRIVER_EVENT_TARGETS = {
    "volume": "units",
    "unit_cogs": "unit_cogs",
    "discount_rate": "discount_rate",
}
SUPPORTED_EVENT_TYPES = set(DRIVER_EVENT_TARGETS) | {"opex"}
SUPPORTED_OPERATIONS = {"multiply", "add"}
DRIVER_KEYS = ["period_date", "country", "product", "segment"]


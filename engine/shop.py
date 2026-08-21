"""Millhaven's shopkeeper: which entity id sells what. Price itself lives on
ItemDef.cost (content/schema.py), not here - a price is a fact about the
item, not about this one shopkeeper. This module only holds the one-off
fact of which catalog entity is a shopkeeper and what they stock."""

from __future__ import annotations

SHOPKEEPER_ENTITY_ID = "shopkeeper"
SHOP_INVENTORY: list[str] = ["healing_potion"]

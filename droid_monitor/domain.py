"""Domain rules for turning OCR text into user-visible alerts."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class AlertRule:
    """A material and rarity combination worth notifying about."""

    id: str
    emoji: str
    label: str
    material: str
    rarity: str


@dataclass(frozen=True)
class RecognizedSpawn:
    """A spawn entry whose material and rarity were both recognized."""

    event: str
    material: str
    rarity: str

    @property
    def label(self) -> str:
        return f"{self.material} {self.rarity.title()}"


# This order is also the order shown in the desktop alert-rule controls.
ALERT_RULES: tuple[AlertRule, ...] = (
    AlertRule("stellar_mythic", "\u2b50", "Stellar Mythic", "Stellar", "mythic"),
    AlertRule("stellar_legendary", "\u2b50", "Stellar Legendary", "Stellar", "legendary"),
    AlertRule("stellar_epic", "\u2b50", "Stellar Epic", "Stellar", "epic"),
    AlertRule("galatic_mythic", "\U0001f30c", "Galactic Mythic", "Galactic", "mythic"),
    AlertRule("galatic_legendary", "\U0001f30c", "Galactic Legendary", "Galactic", "legendary"),
    AlertRule("galatic_epic", "\U0001f30c", "Galactic Epic", "Galactic", "epic"),
    AlertRule("beskar_mythic", "\u26aa", "Beskar Mythic", "Beskar", "mythic"),
    AlertRule("beskar_legendary", "\u26aa", "Beskar Legendary", "Beskar", "legendary"),
    AlertRule("beskar_epic", "\u26aa", "Beskar Epic", "Beskar", "epic"),
    AlertRule("rainbow_mythic", "\U0001f308", "Rainbow Mythic", "Rainbow", "mythic"),
    AlertRule("rainbow_legendary", "\U0001f308", "Rainbow Legendary", "Rainbow", "legendary"),
    AlertRule("rainbow_epic", "\U0001f308", "Rainbow Epic", "Rainbow", "epic"),
    AlertRule("diamond_mythic", "\U0001f48e", "Diamond Mythic", "Diamond", "mythic"),
    AlertRule("diamond_legendary", "\U0001f48e", "Diamond Legendary", "Diamond", "legendary"),
)

DEFAULT_ENABLED_RULE_IDS = frozenset(rule.id for rule in ALERT_RULES)
STELLAR_RULE_IDS = frozenset(rule.id for rule in ALERT_RULES if rule.material == "Stellar")

# Test Mode recognizes all standard item rarities, including combinations that
# are not configured as desktop alerts.
_MATERIALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Stellar", ("stellar",)),
    ("Beskar", ("beskar",)),
    ("Rainbow", ("rainbow", "ainbow", "rainb", "ranbow")),
    ("Galactic", ("galatic", "galactic")),
    ("Diamond", ("diamond",)),
)
_RARITIES = ("uncommon", "common", "rare", "epic", "legendary", "mythic")

# OCR is expected to return a full log entry. The expression intentionally only
# returns entries with the game's spawn wording; ordinary chat and UI labels are
# not alerts.
_SPAWN_EVENT = re.compile(
    r"([A-Za-z][A-Za-z -]*?\s+Droid\s*\([^)]+\))[ \t]+"
    r"spawned\s+at\s+the\s+Sandcrawler",
    re.IGNORECASE,
)


def extract_spawn_events(raw_text: str) -> list[str]:
    """Return the relevant spawn entries found in OCR output, in screen order."""

    if not raw_text:
        return []
    return [match.group(0).strip() for match in _SPAWN_EVENT.finditer(raw_text)]


def parse_spawn_event(event: str) -> RecognizedSpawn | None:
    """Return a recognized material/rarity callout, or ``None`` when incomplete."""

    lowered = event.casefold()
    compacted = re.sub(r"\s+", "", lowered)
    material = next(
        (
            label
            for label, keywords in _MATERIALS
            if any(keyword in compacted for keyword in keywords)
        ),
        None,
    )
    rarity = next(
        (keyword for keyword in _RARITIES if re.search(rf"\b{keyword}\b", lowered)),
        None,
    )
    if not material or not rarity:
        return None
    return RecognizedSpawn(event=event, material=material, rarity=rarity)


def match_alert(event: str, enabled_rule_ids: Iterable[str]) -> AlertRule | None:
    """Return the first enabled alert rule that matches an event, if any."""

    recognized = parse_spawn_event(event)
    if not recognized:
        return None

    enabled = set(enabled_rule_ids)
    for rule in ALERT_RULES:
        if (
            rule.id in enabled
            and rule.material == recognized.material
            and rule.rarity == recognized.rarity
        ):
            return rule
    return None

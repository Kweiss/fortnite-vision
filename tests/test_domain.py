import unittest

from droid_monitor.domain import ALERT_RULES, extract_spawn_events, match_alert, parse_spawn_event


class DomainTests(unittest.TestCase):
    def test_extracts_spawn_events_and_ignores_other_lines(self) -> None:
        text = """
        chat message
        Beskar Droid (Mythic) spawned at the Sandcrawler
        Diamond Droid (Epic) spawned at the Sandcrawler
        """

        self.assertEqual(
            extract_spawn_events(text),
            [
                "Beskar Droid (Mythic) spawned at the Sandcrawler",
                "Diamond Droid (Epic) spawned at the Sandcrawler",
            ],
        )

    def test_match_alert_respects_the_enabled_rule_set(self) -> None:
        event = "Beskar Droid (Mythic) spawned at the Sandcrawler"
        stellar_event = "Stellar Droid (Epic) spawned at the Sandcrawler"

        self.assertEqual(match_alert(event, {"beskar_mythic"}).id, "beskar_mythic")
        self.assertEqual(match_alert(stellar_event, {"stellar_epic"}).id, "stellar_epic")
        self.assertIsNone(match_alert(event, {"rainbow_mythic"}))

    def test_rainbow_rule_tolerates_expected_ocr_misspelling(self) -> None:
        event = "Ainbow Droid (Mythic) spawned at the Sandcrawler"

        self.assertEqual(match_alert(event, {"rainbow_mythic"}).id, "rainbow_mythic")

    def test_test_mode_parser_recognizes_unselected_item_callouts(self) -> None:
        diamond = "Diamond Droid (Common) spawned at the Sandcrawler"
        galactic = "Galactic Droid (Legendary) spawned at the Sandcrawler"
        split_rainbow = "Ra nbow Droid (Epic) spawned at the Sandcrawler"
        stellar = "Stellar Droid (Common) spawned at the Sandcrawler"

        self.assertEqual(parse_spawn_event(diamond).label, "Diamond Common")
        self.assertEqual(parse_spawn_event(galactic).label, "Galactic Legendary")
        self.assertEqual(parse_spawn_event(split_rainbow).label, "Rainbow Epic")
        self.assertEqual(parse_spawn_event(stellar).label, "Stellar Common")
        self.assertIsNone(match_alert(diamond, {"beskar_mythic"}))

    def test_alert_rules_follow_the_requested_order_and_labels(self) -> None:
        self.assertEqual(
            [rule.label for rule in ALERT_RULES],
            [
                "Stellar Mythic",
                "Stellar Legendary",
                "Stellar Epic",
                "Galactic Mythic",
                "Galactic Legendary",
                "Galactic Epic",
                "Beskar Mythic",
                "Beskar Legendary",
                "Beskar Epic",
                "Rainbow Mythic",
                "Rainbow Legendary",
                "Rainbow Epic",
                "Diamond Mythic",
                "Diamond Legendary",
            ],
        )

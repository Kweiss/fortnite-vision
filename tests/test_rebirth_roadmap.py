import unittest

from droid_monitor.rebirth_roadmap import hold_advice, requirements_for, upcoming_requirements


class RebirthRoadmapTests(unittest.TestCase):
    def test_path_two_rank_twenty_six_matches_the_supplied_sheet(self) -> None:
        requirement = requirements_for(2, 26)

        self.assertIsNotNone(requirement)
        self.assertEqual(requirement.credits, "21T")  # type: ignore[union-attr]
        self.assertEqual(
            [droid.label for droid in requirement.droids],  # type: ignore[union-attr]
            [
                "KX Gold Mythic",
                "DRFT-R Diamond Mythic",
                "IG Rainbow Mythic",
            ],
        )

    def test_path_two_roller_targets_follow_rank_twenty_six(self) -> None:
        upcoming = upcoming_requirements(2, 26)

        self.assertEqual([requirement.rank for requirement in upcoming], [27, 28, 29, 30])
        self.assertEqual(
            [droid.label for droid in upcoming[0].droids],
            [
                "LEP Diamond Mythic",
                "Loadlifter Rainbow Mythic",
                "MO-TRAK Beskar Mythic",
            ],
        )

    def test_path_two_identifies_hold_upgrade_and_no_later_need(self) -> None:
        advice_by_name = {item.droid.name: item for item in hold_advice(2, 26)}

        self.assertTrue(advice_by_name["KX"].needs_upgrade)
        self.assertEqual(advice_by_name["KX"].later_requirement.rank, 30)  # type: ignore[union-attr]
        self.assertEqual(advice_by_name["KX"].later_droid.label, "KX Beskar Mythic")  # type: ignore[union-attr]
        self.assertTrue(advice_by_name["DRFT-R"].needs_upgrade)
        self.assertEqual(advice_by_name["IG"].later_requirement, None)

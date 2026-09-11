"""Curated late-Path Rebirth requirements used for roller planning."""

from __future__ import annotations

from dataclasses import dataclass


_CREDITS_BY_RANK = {
    21: "3T",
    22: "4.5T",
    23: "6T",
    24: "9T",
    25: "13.5T",
    26: "21T",
    27: "32T",
    28: "45T",
    29: "68T",
    30: "100T",
}
_MATERIAL_ORDER = {"Default": 0, "Gold": 1, "Diamond": 2, "Rainbow": 3, "Beskar": 4, "Galactic": 5}
_RARITY_ORDER = {"Common": 0, "Rare": 1, "Epic": 2, "Legendary": 3, "Mythic": 4}


@dataclass(frozen=True)
class RoadmapDroid:
    name: str
    material: str
    rarity: str

    @property
    def label(self) -> str:
        return f"{self.name} {self.material} {self.rarity}"


@dataclass(frozen=True)
class RoadmapRank:
    path: int
    rank: int
    credits: str
    droids: tuple[RoadmapDroid, ...]


@dataclass(frozen=True)
class DroidHoldAdvice:
    droid: RoadmapDroid
    later_requirement: RoadmapRank | None
    later_droid: RoadmapDroid | None
    needs_upgrade: bool = False


def requirements_for(path: int | None, rank: int | None) -> RoadmapRank | None:
    if path is None or rank is None:
        return None
    return _ROADMAP.get(path, {}).get(rank)


def upcoming_requirements(path: int | None, rank: int | None, count: int = 4) -> tuple[RoadmapRank, ...]:
    if path is None or rank is None:
        return ()
    path_requirements = _ROADMAP.get(path, {})
    return tuple(
        row
        for future_rank, row in sorted(path_requirements.items())
        if future_rank > rank
    )[:count]


def hold_advice(path: int | None, rank: int | None) -> tuple[DroidHoldAdvice, ...]:
    """Return per-droid advice for the current target through the end of its Path."""

    current = requirements_for(path, rank)
    if current is None:
        return ()
    later_rows = upcoming_requirements(path, rank, count=30)
    advice: list[DroidHoldAdvice] = []
    for droid in current.droids:
        later_matches = [
            (row, candidate)
            for row in later_rows
            for candidate in row.droids
            if candidate.name.casefold() == droid.name.casefold()
        ]
        if not later_matches:
            advice.append(DroidHoldAdvice(droid, None, None))
            continue
        later_row, later_droid = max(
            later_matches,
            key=lambda match: (_quality(match[1]), -match[0].rank),
        )
        advice.append(
            DroidHoldAdvice(
                droid=droid,
                later_requirement=later_row,
                later_droid=later_droid,
                needs_upgrade=_quality(later_droid) > _quality(droid),
            )
        )
    return tuple(advice)


def _quality(droid: RoadmapDroid) -> tuple[int, int]:
    return (_MATERIAL_ORDER[droid.material], _RARITY_ORDER[droid.rarity])


def _row(path: int, rank: int, *droids: tuple[str, str, str]) -> RoadmapRank:
    return RoadmapRank(
        path=path,
        rank=rank,
        credits=_CREDITS_BY_RANK[rank],
        droids=tuple(RoadmapDroid(*droid) for droid in droids),
    )


_ROADMAP = {
    1: {
        21: _row(1, 21, ("BB", "Beskar", "Epic"), ("Orb-Walker", "Beskar", "Epic"), ("Groundmech", "Beskar", "Epic")),
        22: _row(1, 22, ("AMP Walker", "Beskar", "Epic"), ("B1 Heavy", "Beskar", "Epic"), ("Proto-Roller", "Beskar", "Legendary")),
        23: _row(1, 23, ("OPTI-STRK", "Beskar", "Legendary"), ("Mono-WLKR", "Beskar", "Legendary"), ("R7", "Beskar", "Legendary")),
        24: _row(1, 24, ("BB9", "Beskar", "Legendary"), ("Cyclo-Grav", "Beskar", "Legendary"), ("MO-TRAK", "Default", "Mythic")),
        25: _row(1, 25, ("B2-RP", "Beskar", "Legendary"), ("IG", "Default", "Mythic"), ("DRFT-R", "Gold", "Mythic")),
        26: _row(1, 26, ("Cyclens", "Gold", "Mythic"), ("Loadlifter", "Diamond", "Mythic"), ("RIC-1200", "Rainbow", "Mythic")),
        27: _row(1, 27, ("KX", "Diamond", "Mythic"), ("TRI-TEK", "Rainbow", "Mythic"), ("Snow Mouse", "Beskar", "Mythic")),
        28: _row(1, 28, ("MO-TRAK", "Rainbow", "Mythic"), ("DRFT-R", "Beskar", "Mythic"), ("Proto-Roller", "Galactic", "Mythic")),
        29: _row(1, 29, ("IG", "Beskar", "Mythic"), ("Mono-WLKR", "Galactic", "Legendary"), ("Mecha-Droid", "Galactic", "Legendary")),
        30: _row(1, 30, ("Cyclens", "Beskar", "Mythic"), ("B2-RP", "Galactic", "Legendary"), ("Loadlifter", "Galactic", "Mythic")),
    },
    2: {
        21: _row(2, 21, ("LO", "Beskar", "Epic"), ("R6", "Beskar", "Epic"), ("Haul-R", "Beskar", "Epic")),
        22: _row(2, 22, ("SEN-TRI", "Beskar", "Epic"), ("Strike-Orb", "Beskar", "Epic"), ("Proto-Roller", "Beskar", "Legendary")),
        23: _row(2, 23, ("BB9", "Beskar", "Legendary"), ("Cyclo-Grav", "Beskar", "Legendary"), ("B2-RP", "Beskar", "Legendary")),
        24: _row(2, 24, ("OPTI-STRK", "Beskar", "Legendary"), ("B2-RP", "Beskar", "Legendary"), ("Snow Mouse", "Default", "Mythic")),
        25: _row(2, 25, ("Mono-WLKR", "Beskar", "Legendary"), ("TRI-TEK", "Gold", "Mythic"), ("RIC-1200", "Default", "Mythic")),
        26: _row(2, 26, ("KX", "Gold", "Mythic"), ("DRFT-R", "Diamond", "Mythic"), ("IG", "Rainbow", "Mythic")),
        27: _row(2, 27, ("LEP", "Diamond", "Mythic"), ("Loadlifter", "Rainbow", "Mythic"), ("MO-TRAK", "Beskar", "Mythic")),
        28: _row(2, 28, ("Snow Mouse", "Rainbow", "Mythic"), ("TRI-TEK", "Beskar", "Mythic"), ("Mecha-Droid", "Galactic", "Legendary")),
        29: _row(2, 29, ("RIC", "Beskar", "Mythic"), ("Cyclo-Grav", "Galactic", "Legendary"), ("R7", "Galactic", "Legendary")),
        30: _row(2, 30, ("KX", "Beskar", "Mythic"), ("OPTI-STRK", "Galactic", "Legendary"), ("DRFT-R", "Galactic", "Mythic")),
    },
    3: {
        21: _row(3, 21, ("B2 Super", "Beskar", "Epic"), ("OPTI-POD", "Beskar", "Epic"), ("R2", "Beskar", "Epic")),
        22: _row(3, 22, ("Gunrunner", "Beskar", "Epic"), ("LNG-SHOT", "Beskar", "Epic"), ("B2-RP", "Beskar", "Legendary")),
        23: _row(3, 23, ("Mono-WLKR", "Beskar", "Legendary"), ("Mecha-Droid", "Beskar", "Legendary"), ("Cyclo-Grav", "Beskar", "Legendary")),
        24: _row(3, 24, ("BB9", "Beskar", "Legendary"), ("B2-RP", "Beskar", "Legendary"), ("RIC", "Default", "Mythic")),
        25: _row(3, 25, ("Proto-Roller", "Beskar", "Legendary"), ("Loadlifter", "Default", "Mythic"), ("MO-TRAK", "Gold", "Mythic")),
        26: _row(3, 26, ("LEP", "Gold", "Mythic"), ("TRI-TEK", "Diamond", "Mythic"), ("Snow Mouse", "Rainbow", "Mythic")),
        27: _row(3, 27, ("RIC-1200", "Diamond", "Mythic"), ("IG", "Rainbow", "Mythic"), ("DRFT-R", "Beskar", "Mythic")),
        28: _row(3, 28, ("RIC", "Rainbow", "Mythic"), ("MO-TRAK", "Beskar", "Mythic"), ("BB9", "Galactic", "Legendary")),
        29: _row(3, 29, ("IG", "Beskar", "Mythic"), ("Mecha-Droid", "Galactic", "Legendary"), ("OPTI-STRK", "Galactic", "Legendary")),
        30: _row(3, 30, ("LEP", "Beskar", "Mythic"), ("R7", "Galactic", "Legendary"), ("DRFT-R", "Galactic", "Mythic")),
    },
    4: {
        21: _row(4, 21, ("Haul-R", "Beskar", "Epic"), ("Groundmech", "Beskar", "Epic"), ("AMP Walker", "Beskar", "Epic")),
        22: _row(4, 22, ("Gunrunner", "Beskar", "Epic"), ("Strike-Orb", "Beskar", "Epic"), ("B2 Super", "Beskar", "Epic")),
        23: _row(4, 23, ("Mono-WLKR", "Beskar", "Legendary"), ("Cyclo-Grav", "Beskar", "Legendary"), ("B2-RP", "Beskar", "Legendary")),
        24: _row(4, 24, ("Mecha-Droid", "Beskar", "Legendary"), ("Proto-Roller", "Beskar", "Legendary"), ("MO-TRAK", "Default", "Mythic")),
        25: _row(4, 25, ("OPTI-STRK", "Beskar", "Legendary"), ("TRI-TEK", "Default", "Mythic"), ("DRFT-R", "Gold", "Mythic")),
        26: _row(4, 26, ("Cyclens", "Gold", "Mythic"), ("LEP", "Diamond", "Mythic"), ("MO-TRAK", "Rainbow", "Mythic")),
        27: _row(4, 27, ("RIC-1200", "Diamond", "Mythic"), ("Snow Mouse", "Rainbow", "Mythic"), ("Loadlifter", "Beskar", "Mythic")),
        28: _row(4, 28, ("IG", "Rainbow", "Mythic"), ("KX", "Beskar", "Mythic"), ("OPTI-STRK", "Galactic", "Legendary")),
        29: _row(4, 29, ("TRI-TEK", "Beskar", "Mythic"), ("R7", "Galactic", "Legendary"), ("BB9", "Galactic", "Legendary")),
        30: _row(4, 30, ("Cyclens", "Beskar", "Mythic"), ("Mono-WLKR", "Galactic", "Legendary"), ("IG", "Galactic", "Mythic")),
    },
}

"""Tests pour data.geo (rayon Haversine + sélection communes)."""

import math

import pytest

from data.geo import (
    all_known_commune_names,
    communes_within_radius,
    haversine_km,
)
from data.commune_coords import BELGIAN_COMMUNE_COORDS, _normalize_commune_name


class TestHaversine:
    def test_zero_distance_for_same_point(self):
        p = (50.7172, 4.3995)  # Waterloo
        assert haversine_km(p, p) == pytest.approx(0.0, abs=1e-6)

    def test_known_distance_brussels_liege(self):
        # Bruxelles ↔ Liège ≈ 84 km à vol d'oiseau (validé sur Google Maps)
        bxl = BELGIAN_COMMUNE_COORDS["bruxelles"]
        lge = BELGIAN_COMMUNE_COORDS["liege"]
        d = haversine_km(bxl, lge)
        assert 80 <= d <= 90, f"Bruxelles↔Liège devrait être ~84 km, calculé {d:.1f}"

    def test_known_distance_waterloo_braine(self):
        # Waterloo ↔ Braine-l'Alleud ≈ 3 km
        wl = BELGIAN_COMMUNE_COORDS["waterloo"]
        ba = BELGIAN_COMMUNE_COORDS["braine-lalleud"]
        d = haversine_km(wl, ba)
        assert 2 <= d <= 5, f"Waterloo↔Braine devrait être ~3 km, calculé {d:.1f}"

    def test_symmetric(self):
        a, b = (51.0, 4.0), (50.5, 4.5)
        assert haversine_km(a, b) == pytest.approx(haversine_km(b, a), abs=1e-9)


class TestCommunesWithinRadius:
    def test_waterloo_5km(self):
        # Dans un rayon de 5 km autour de Waterloo, on doit avoir au moins
        # Waterloo et Braine-l'Alleud
        result = communes_within_radius("Waterloo", 5)
        names = [n for n, _ in result]
        names_lower = [n.lower() for n in names]
        assert any("waterloo" in n for n in names_lower)
        assert any("braine" in n for n in names_lower)
        # Distance triée croissante
        distances = [d for _, d in result]
        assert distances == sorted(distances)

    def test_waterloo_includes_self_by_default(self):
        result = communes_within_radius("Waterloo", 5)
        names_norm = [_normalize_commune_name(n) for n, _ in result]
        assert "waterloo" in names_norm

    def test_waterloo_can_exclude_self(self):
        result = communes_within_radius("Waterloo", 5, include_center=False)
        names_norm = [_normalize_commune_name(n) for n, _ in result]
        assert "waterloo" not in names_norm

    def test_unknown_center_returns_empty(self):
        # Une commune complètement inventée
        assert communes_within_radius("Villelibre-sur-Inconnu", 100) == []

    def test_radius_grows_monotonically(self):
        small = communes_within_radius("Bruxelles", 5)
        large = communes_within_radius("Bruxelles", 30)
        assert len(large) >= len(small), (
            "Un rayon plus large doit inclure au moins autant de communes"
        )

    def test_zero_radius_returns_only_center(self):
        # Avec rayon 0 et include_center=True, on doit avoir UNIQUEMENT le centre
        result = communes_within_radius("Waterloo", 0)
        assert len(result) == 1
        assert _normalize_commune_name(result[0][0]) == "waterloo"

    def test_distance_values_are_within_radius(self):
        radius = 15
        result = communes_within_radius("Liège", radius)
        for name, dist in result:
            assert dist <= radius, f"{name} à {dist:.1f} km > rayon {radius}"

    def test_case_insensitive_center(self):
        # Le centre peut être passé dans n'importe quelle casse
        a = communes_within_radius("WATERLOO", 5)
        b = communes_within_radius("waterloo", 5)
        c = communes_within_radius("Waterloo", 5)
        assert a == b == c


class TestNormalization:
    @pytest.mark.parametrize("inp,expected", [
        ("Waterloo", "waterloo"),
        ("Braine-l'Alleud", "braine-lalleud"),
        ("LIÈGE", "liege"),
        ("  Mons  ", "mons"),
        ("Ottignies-Louvain-la-Neuve", "ottignies-louvain-la-neuve"),
        ("", ""),
    ])
    def test_normalize(self, inp, expected):
        assert _normalize_commune_name(inp) == expected


class TestKnownCommunesList:
    def test_returns_sorted_unique_list(self):
        names = all_known_commune_names()
        assert names == sorted(names)
        assert len(names) == len(set(names))

    def test_covers_major_cities(self):
        names = [_normalize_commune_name(n) for n in all_known_commune_names()]
        # Les capitales / villes principales DOIVENT être présentes.
        # On accepte FR ou NL (les arrondissements utilisent l'un OU l'autre
        # selon la province), donc on cherche au moins un des alias.
        for aliases in [
            ("bruxelles",),
            ("liege",),
            ("namur",),
            ("mons",),
            ("charleroi",),
            ("antwerpen", "anvers"),
            ("gent", "gand"),
            ("brugge", "bruges"),
            ("leuven", "louvain"),
            ("waterloo",),
        ]:
            assert any(a in names for a in aliases), (
                f"Aucun alias de {aliases} dans le dataset géolocalisé"
            )

    def test_size_is_reasonable(self):
        # Sanity check : on doit avoir entre 100 et 600 communes
        # (en-dessous = dataset trop pauvre, au-dessus = bug de doublons)
        n = len(all_known_commune_names())
        assert 100 <= n <= 600, f"Dataset taille suspecte : {n} communes"

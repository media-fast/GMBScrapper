"""Calculs géographiques pour la sélection de communes par rayon.

Utilise la formule de Haversine (sphère, R=6371 km). Précision : ±0.5 % à
l'échelle d'un pays comme la Belgique, largement suffisante pour "trouver
les communes à 15 km autour de Waterloo".
"""

import math
from typing import Iterable

from .belgian_arrondissements import ARRONDISSEMENTS
from .commune_coords import BELGIAN_COMMUNE_COORDS, _normalize_commune_name


EARTH_RADIUS_KM = 6371.0


def haversine_km(coord_a: tuple[float, float], coord_b: tuple[float, float]) -> float:
    """Distance en km entre deux points (lat, lng) sur la sphère terrestre."""
    lat1, lng1 = coord_a
    lat2, lng2 = coord_b
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


def _all_known_communes_with_coords() -> list[tuple[str, tuple[float, float]]]:
    """Inventaire de toutes les communes belges connues, en utilisant les
    noms canoniques (avec accents/apostrophes) des arrondissements quand
    possible, et leurs coords issues de commune_coords.

    Retourne une liste de (nom_canonique, (lat, lng)). Si une commune des
    ARRONDISSEMENTS n'a pas de coords, elle est exclue (sans erreur — l'user
    peut toujours utiliser le mode "Par commune" classique).
    """
    seen_norms: set[str] = set()
    result: list[tuple[str, tuple[float, float]]] = []
    for info in ARRONDISSEMENTS.values():
        for commune in info["communes"]:
            norm = _normalize_commune_name(commune)
            if norm in seen_norms:
                continue
            coords = BELGIAN_COMMUNE_COORDS.get(norm)
            if coords:
                seen_norms.add(norm)
                result.append((commune, coords))
    return result


def communes_within_radius(
    center_name: str,
    radius_km: float,
    *,
    include_center: bool = True,
) -> list[tuple[str, float]]:
    """Liste les communes belges à moins de `radius_km` du centre, triées
    par distance croissante.

    Args:
        center_name: nom de la commune centrale (libre, normalisé en interne).
        radius_km: rayon en kilomètres.
        include_center: si True, la commune centrale est incluse (dist=0).

    Returns:
        list[(nom_canonique, distance_km)] triée par distance.
        Liste vide si `center_name` n'est pas dans le dataset des coords.
    """
    center_coords = BELGIAN_COMMUNE_COORDS.get(_normalize_commune_name(center_name))
    if center_coords is None:
        return []

    center_norm = _normalize_commune_name(center_name)
    results: list[tuple[str, float]] = []
    for canonical, coords in _all_known_communes_with_coords():
        dist = haversine_km(center_coords, coords)
        if dist <= radius_km:
            is_center = _normalize_commune_name(canonical) == center_norm
            if is_center and not include_center:
                continue
            results.append((canonical, dist))
    results.sort(key=lambda x: x[1])
    return results


def all_known_commune_names() -> list[str]:
    """Liste triée des noms canoniques de communes disponibles pour le
    sélecteur "ville centrale" du mode rayon.
    """
    names = sorted({c for c, _ in _all_known_communes_with_coords()})
    return names

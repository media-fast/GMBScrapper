import re
import unicodedata

from rapidfuzz import fuzz

from .models import Business


BELGIAN_CITY_POSTALS = {
    "waterloo": ["1410"],
    "braine-l'alleud": ["1420"],
    "braine l'alleud": ["1420"],
    "braine-lalleud": ["1420"],
    "nivelles": ["1400", "1401", "1402"],
    "la hulpe": ["1310"],
    "halle": ["1500", "1501", "1502"],
    "bruxelles": ["1000", "1020", "1030", "1040", "1050", "1060", "1070", "1080",
                  "1081", "1082", "1083", "1090", "1120", "1130", "1140", "1150",
                  "1160", "1170", "1180", "1190", "1200", "1210"],
    "ixelles": ["1050"],
    "uccle": ["1180"],
    "schaerbeek": ["1030"],
    "anderlecht": ["1070"],
    "louvain-la-neuve": ["1348"],
    "ottignies": ["1340", "1341", "1342"],
    "wavre": ["1300", "1301"],
    "rixensart": ["1330", "1331", "1332"],
    "genval": ["1332"],
    "court-saint-etienne": ["1490"],
    "tubize": ["1480"],
    "rebecq": ["1430"],
    "ittre": ["1460"],
    "lasne": ["1380"],
    "namur": ["5000", "5001", "5002", "5003", "5004"],
    "liege": ["4000", "4020", "4030", "4031", "4032"],
    "charleroi": ["6000", "6010", "6020", "6030", "6031", "6032", "6040", "6041", "6042", "6043", "6044"],
    "mons": ["7000", "7010", "7011", "7012", "7020", "7021", "7022", "7030", "7032", "7033", "7034"],
    "tournai": ["7500", "7501", "7502", "7503", "7504", "7520", "7521", "7522", "7530", "7531", "7532", "7533", "7536", "7538", "7540", "7542", "7543", "7548"],
    "anvers": ["2000", "2018", "2020", "2030", "2040", "2050", "2060"],
    "antwerpen": ["2000", "2018", "2020", "2030", "2040", "2050", "2060"],
    "gand": ["9000", "9030", "9031", "9032", "9040", "9041", "9042", "9050", "9051", "9052"],
    "gent": ["9000", "9030", "9031", "9032", "9040", "9041", "9042", "9050", "9051", "9052"],
    "bruges": ["8000", "8200", "8310", "8380"],
    "brugge": ["8000", "8200", "8310", "8380"],
    "leuven": ["3000", "3001", "3010", "3012", "3018"],
    "louvain": ["3000", "3001", "3010", "3012", "3018"],
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().strip()
    s = re.sub(r"[^\w\s\-']", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def known_postal_codes(city: str) -> list[str]:
    return BELGIAN_CITY_POSTALS.get(_norm(city), [])


def matches_city(business: Business, fuzzy_threshold: int = 80) -> bool:
    if not business.city:
        return True

    target_norm = _norm(business.city)
    known_codes = known_postal_codes(business.city)

    if business.postal_code and known_codes and business.postal_code in known_codes:
        return True

    if business.locality:
        score = fuzz.token_set_ratio(target_norm, _norm(business.locality))
        if score >= fuzzy_threshold:
            return True

    if business.address:
        score = fuzz.partial_ratio(target_norm, _norm(business.address))
        if score >= fuzzy_threshold + 5:
            return True

    return False


def filter_by_city(businesses: list[Business], fuzzy_threshold: int = 80) -> tuple[list[Business], list[Business]]:
    kept: list[Business] = []
    dropped: list[Business] = []
    for b in businesses:
        if matches_city(b, fuzzy_threshold):
            kept.append(b)
        else:
            dropped.append(b)
    return kept, dropped

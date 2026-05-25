"""Coordonnées GPS (lat, lng) des principales communes belges.

Dataset volontairement limité aux ~150 communes les plus peuplées de Belgique
pour permettre la recherche par rayon (Haversine) sans dépendance externe.
Couvre Bruxelles, les 19 communes BXL, et les chefs-lieux/villes principales
des 10 provinces wallonnes et flamandes.

Pour ajouter une commune : récupérer ses coords sur https://opendatasoft.com/
ou OpenStreetMap, et ajouter une entrée `"nom_normalise": (lat, lng)`.

Le nom est normalisé via `_normalize_commune_name()` (lowercase, sans accents,
sans apostrophe). Les recherches utilisent ce même normaliseur pour matcher
"Braine-l'Alleud" et "braine lalleud" sur la même entrée.
"""

import unicodedata


def _normalize_commune_name(name: str) -> str:
    """Normalise pour le lookup : lowercase + sans accents + sans apostrophes."""
    if not name:
        return ""
    n = unicodedata.normalize("NFD", name)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    n = n.lower().strip()
    # Apostrophes courbes/droites + tirets bas
    for ch in ("'", "'", "`", "_"):
        n = n.replace(ch, "")
    return n


# Format : { nom_normalisé : (latitude, longitude) }
# Sources : OpenStreetMap / WikiData (chefs-lieux et grandes villes belges).
BELGIAN_COMMUNE_COORDS: dict[str, tuple[float, float]] = {
    # ─── Région de Bruxelles-Capitale (19 communes) ───────────────────────
    "anderlecht":                  (50.8367, 4.3076),
    "auderghem":                   (50.8125, 4.4280),
    "berchem-sainte-agathe":       (50.8651, 4.2925),
    "bruxelles":                   (50.8503, 4.3517),
    "etterbeek":                   (50.8358, 4.3851),
    "evere":                       (50.8675, 4.4011),
    "forest":                      (50.8128, 4.3266),
    "ganshoren":                   (50.8702, 4.3017),
    "ixelles":                     (50.8333, 4.3667),
    "jette":                       (50.8780, 4.3286),
    "koekelberg":                  (50.8631, 4.3239),
    "molenbeek-saint-jean":        (50.8550, 4.3260),
    "saint-gilles":                (50.8275, 4.3461),
    "saint-josse-ten-noode":       (50.8521, 4.3697),
    "schaerbeek":                  (50.8676, 4.3737),
    "uccle":                       (50.8004, 4.3375),
    "watermael-boitsfort":         (50.7967, 4.4117),
    "woluwe-saint-lambert":        (50.8475, 4.4297),
    "woluwe-saint-pierre":         (50.8398, 4.4400),

    # ─── Brabant wallon ───────────────────────────────────────────────────
    "beauvechain":                 (50.7833, 4.7833),
    "braine-lalleud":              (50.6826, 4.3699),
    "chastre":                     (50.6258, 4.6311),
    "chaumont-gistoux":            (50.7178, 4.6678),
    "court-saint-etienne":         (50.6300, 4.5689),
    "genappe":                     (50.6122, 4.4567),
    "grez-doiceau":                (50.7378, 4.7011),
    "helecine":                    (50.7378, 4.9989),
    "incourt":                     (50.6783, 4.8500),
    "ittre":                       (50.6478, 4.2667),
    "jodoigne":                    (50.7239, 4.8678),
    "la hulpe":                    (50.7300, 4.4859),
    "lasne":                       (50.6789, 4.4878),
    "mont-saint-guibert":          (50.6378, 4.6178),
    "nivelles":                    (50.5980, 4.3239),
    "orp-jauche":                  (50.6839, 4.9750),
    "ottignies-louvain-la-neuve":  (50.6649, 4.5677),
    "ottignies":                   (50.6649, 4.5677),
    "perwez":                      (50.6300, 4.8067),
    "ramillies":                   (50.6500, 4.9039),
    "rebecq":                      (50.6539, 4.1417),
    "rixensart":                   (50.7144, 4.5306),
    "tubize":                      (50.6912, 4.2010),
    "villers-la-ville":            (50.5811, 4.5189),
    "walhain":                     (50.6500, 4.6911),
    "waterloo":                    (50.7172, 4.3995),
    "wavre":                       (50.7173, 4.6068),

    # ─── Hainaut ──────────────────────────────────────────────────────────
    "ath":                         (50.6306, 3.7783),
    "beloeil":                     (50.5500, 3.7333),
    "binche":                      (50.4117, 4.1672),
    "boussu":                      (50.4339, 3.7950),
    "braine-le-comte":             (50.6075, 4.1369),
    "charleroi":                   (50.4108, 4.4446),
    "chatelet":                    (50.4022, 4.5267),
    "chievres":                    (50.5867, 3.8083),
    "comines-warneton":            (50.7672, 2.9883),
    "courcelles":                  (50.4694, 4.3789),
    "ecaussinnes":                 (50.5739, 4.1683),
    "enghien":                     (50.6900, 4.0322),
    "estaimpuis":                  (50.7178, 3.2528),
    "estinnes":                    (50.4150, 4.1100),
    "fleurus":                     (50.4839, 4.5478),
    "frasnes-lez-anvaing":         (50.6711, 3.6233),
    "gerpinnes":                   (50.3358, 4.5217),
    "hensies":                     (50.4364, 3.6711),
    "honnelles":                   (50.3611, 3.7228),
    "la louviere":                 (50.4778, 4.1858),
    "lessines":                    (50.7100, 3.8333),
    "leuze-en-hainaut":            (50.6042, 3.6178),
    "manage":                      (50.5106, 4.2289),
    "mons":                        (50.4542, 3.9560),
    "morlanwelz":                  (50.4506, 4.2533),
    "mouscron":                    (50.7461, 3.2103),
    "peruwelz":                    (50.5117, 3.5928),
    "quaregnon":                   (50.4456, 3.8617),
    "quevy":                       (50.3850, 3.9322),
    "saint-ghislain":              (50.4500, 3.8167),
    "seneffe":                     (50.5378, 4.2589),
    "silly":                       (50.6517, 3.9272),
    "soignies":                    (50.5783, 4.0689),
    "thuin":                       (50.3417, 4.2867),
    "tournai":                     (50.6056, 3.3893),

    # ─── Liège ────────────────────────────────────────────────────────────
    "amay":                        (50.5483, 5.3083),
    "ans":                         (50.6611, 5.5181),
    "aubel":                       (50.7000, 5.8500),
    "awans":                       (50.6611, 5.4767),
    "blegny":                      (50.6700, 5.7400),
    "chaudfontaine":               (50.5917, 5.6361),
    "dison":                       (50.6111, 5.8500),
    "engis":                       (50.5650, 5.4117),
    "esneux":                      (50.5350, 5.5683),
    "eupen":                       (50.6303, 6.0339),
    "flemalle":                    (50.6017, 5.4633),
    "fleron":                      (50.6128, 5.6661),
    "grace-hollogne":              (50.6378, 5.4711),
    "hannut":                      (50.6711, 5.0789),
    "herstal":                     (50.6628, 5.6261),
    "herve":                       (50.6422, 5.8011),
    "huy":                         (50.5189, 5.2394),
    "liege":                       (50.6326, 5.5797),
    "limbourg":                    (50.6133, 5.9417),
    "malmedy":                     (50.4258, 6.0278),
    "oupeye":                      (50.7000, 5.6500),
    "saint-nicolas":               (50.6444, 5.5350),
    "seraing":                     (50.5833, 5.5061),
    "soumagne":                    (50.6222, 5.7411),
    "spa":                         (50.4928, 5.8639),
    "stavelot":                    (50.3922, 5.9311),
    "verviers":                    (50.5879, 5.8631),
    "vise":                        (50.7361, 5.6975),
    "waremme":                     (50.6961, 5.2553),

    # ─── Luxembourg (BE) ──────────────────────────────────────────────────
    "arlon":                       (49.6837, 5.8164),
    "bastogne":                    (50.0023, 5.7180),
    "bouillon":                    (49.7944, 5.0689),
    "durbuy":                      (50.3528, 5.4564),
    "houffalize":                  (50.1283, 5.7894),
    "marche-en-famenne":           (50.2278, 5.3431),
    "neufchateau":                 (49.8408, 5.4344),
    "saint-hubert":                (50.0286, 5.3744),
    "vielsalm":                    (50.2839, 5.9100),
    "virton":                      (49.5683, 5.5283),

    # ─── Namur ────────────────────────────────────────────────────────────
    "andenne":                     (50.4869, 5.0944),
    "ciney":                       (50.2933, 5.0961),
    "couvin":                      (50.0533, 4.4961),
    "dinant":                      (50.2603, 4.9128),
    "eghezee":                     (50.5853, 4.9089),
    "fosses-la-ville":             (50.3994, 4.6961),
    "gembloux":                    (50.5650, 4.6911),
    "namur":                       (50.4674, 4.8720),
    "philippeville":               (50.1986, 4.5450),
    "rochefort":                   (50.1611, 5.2233),
    "sambreville":                 (50.4500, 4.6167),
    "walcourt":                    (50.2533, 4.4350),

    # ─── Anvers ───────────────────────────────────────────────────────────
    "antwerpen":                   (51.2194, 4.4025),
    "anvers":                      (51.2194, 4.4025),
    "boom":                        (51.0850, 4.3700),
    "geel":                        (51.1656, 4.9931),
    "herentals":                   (51.1789, 4.8311),
    "lier":                        (51.1303, 4.5703),
    "mechelen":                    (51.0258, 4.4775),
    "malines":                     (51.0258, 4.4775),
    "mol":                         (51.1900, 5.1167),
    "schoten":                     (51.2522, 4.5028),
    "turnhout":                    (51.3225, 4.9447),

    # ─── Brabant flamand ──────────────────────────────────────────────────
    "aarschot":                    (50.9856, 4.8369),
    "asse":                        (50.9111, 4.2050),
    "diest":                       (50.9856, 5.0489),
    "halle":                       (50.7333, 4.2378),
    "leuven":                      (50.8798, 4.7005),
    "louvain":                     (50.8798, 4.7005),
    "tienen":                      (50.8064, 4.9356),
    "vilvoorde":                   (50.9281, 4.4264),
    "zaventem":                    (50.8839, 4.4700),

    # ─── Flandre orientale ────────────────────────────────────────────────
    "aalst":                       (50.9378, 4.0408),
    "alost":                       (50.9378, 4.0408),
    "deinze":                      (50.9839, 3.5278),
    "dendermonde":                 (51.0286, 4.1011),
    "eeklo":                       (51.1856, 3.5667),
    "gent":                        (51.0543, 3.7174),
    "gand":                        (51.0543, 3.7174),
    "lokeren":                     (51.1011, 3.9931),
    "ninove":                      (50.8281, 4.0231),
    "oudenaarde":                  (50.8456, 3.6056),
    "ronse":                       (50.7461, 3.6042),
    "sint-niklaas":                (51.1656, 4.1428),
    "wetteren":                    (51.0011, 3.8856),

    # ─── Flandre occidentale ──────────────────────────────────────────────
    "blankenberge":                (51.3122, 3.1306),
    "brugge":                      (51.2093, 3.2247),
    "bruges":                      (51.2093, 3.2247),
    "diksmuide":                   (51.0322, 2.8633),
    "ieper":                       (50.8511, 2.8856),
    "ypres":                       (50.8511, 2.8856),
    "knokke-heist":                (51.3517, 3.2917),
    "kortrijk":                    (50.8278, 3.2647),
    "courtrai":                    (50.8278, 3.2647),
    "menen":                       (50.7972, 3.1247),
    "oostende":                    (51.2247, 2.9081),
    "ostende":                     (51.2247, 2.9081),
    "roeselare":                   (50.9472, 3.1228),
    "tielt":                       (50.9994, 3.3267),
    "waregem":                     (50.8869, 3.4267),

    # ─── Limbourg ─────────────────────────────────────────────────────────
    "beringen":                    (51.0511, 5.2256),
    "bilzen":                      (50.8728, 5.5217),
    "genk":                        (50.9650, 5.5008),
    "hasselt":                     (50.9307, 5.3378),
    "lommel":                      (51.2306, 5.3128),
    "maaseik":                     (51.0989, 5.7878),
    "sint-truiden":                (50.8167, 5.1850),
    "tongeren":                    (50.7806, 5.4644),
}


def get_commune_coords(name: str) -> tuple[float, float] | None:
    """Renvoie (lat, lng) si la commune est connue, None sinon."""
    return BELGIAN_COMMUNE_COORDS.get(_normalize_commune_name(name))


def list_known_communes() -> list[str]:
    """Liste triée des noms normalisés disponibles (~150 communes)."""
    return sorted(BELGIAN_COMMUNE_COORDS.keys())

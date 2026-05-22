"""Arrondissements administratifs belges et leurs communes principales.

Structure : ARRONDISSEMENTS = {
    arrondissement_name: {
        "province": str,
        "region": str,
        "communes": [list of commune names],
    }
}

Source : subdivisions administratives officielles belges (43 arrondissements).
"""

ARRONDISSEMENTS: dict[str, dict] = {
    # ─── Région de Bruxelles-Capitale ─────────────────────────────────────
    "Bruxelles-Capitale": {
        "province": "Bruxelles-Capitale",
        "region": "Bruxelles-Capitale",
        "communes": [
            "Anderlecht", "Auderghem", "Berchem-Sainte-Agathe", "Bruxelles",
            "Etterbeek", "Evere", "Forest", "Ganshoren", "Ixelles", "Jette",
            "Koekelberg", "Molenbeek-Saint-Jean", "Saint-Gilles",
            "Saint-Josse-ten-Noode", "Schaerbeek", "Uccle", "Watermael-Boitsfort",
            "Woluwe-Saint-Lambert", "Woluwe-Saint-Pierre",
        ],
    },

    # ─── Wallonie ─────────────────────────────────────────────────────────
    "Nivelles": {
        "province": "Brabant wallon",
        "region": "Wallonie",
        "communes": [
            "Beauvechain", "Braine-l'Alleud", "Chastre", "Chaumont-Gistoux",
            "Court-Saint-Étienne", "Genappe", "Grez-Doiceau", "Hélécine",
            "Incourt", "Ittre", "Jodoigne", "La Hulpe", "Lasne",
            "Mont-Saint-Guibert", "Nivelles", "Orp-Jauche",
            "Ottignies-Louvain-la-Neuve", "Perwez", "Ramillies", "Rebecq",
            "Rixensart", "Tubize", "Villers-la-Ville", "Walhain", "Waterloo",
            "Wavre",
        ],
    },

    "Ath": {
        "province": "Hainaut",
        "region": "Wallonie",
        "communes": [
            "Ath", "Belœil", "Bernissart", "Brugelette", "Chièvres",
            "Ellezelles", "Flobecq", "Frasnes-lez-Anvaing",
        ],
    },
    "Charleroi": {
        "province": "Hainaut",
        "region": "Wallonie",
        "communes": [
            "Aiseau-Presles", "Chapelle-lez-Herlaimont", "Charleroi", "Châtelet",
            "Courcelles", "Farciennes", "Fleurus", "Fontaine-l'Évêque", "Gerpinnes",
            "Les Bons Villers", "Manage", "Montigny-le-Tilleul", "Pont-à-Celles",
            "Seneffe",
        ],
    },
    "Mons": {
        "province": "Hainaut",
        "region": "Wallonie",
        "communes": [
            "Boussu", "Colfontaine", "Dour", "Frameries", "Hensies", "Honnelles",
            "Jurbise", "Lens", "Le Rœulx", "Mons", "Quaregnon", "Quévy",
            "Quiévrain", "Saint-Ghislain",
        ],
    },
    "Mouscron": {
        "province": "Hainaut",
        "region": "Wallonie",
        "communes": ["Comines-Warneton", "Mouscron"],
    },
    "Soignies": {
        "province": "Hainaut",
        "region": "Wallonie",
        "communes": [
            "Braine-le-Comte", "Écaussinnes", "Enghien", "La Louvière", "Lessines",
            "Silly", "Soignies",
        ],
    },
    "Thuin": {
        "province": "Hainaut",
        "region": "Wallonie",
        "communes": [
            "Anderlues", "Beaumont", "Binche", "Chimay", "Erquelinnes",
            "Estinnes", "Froidchapelle", "Ham-sur-Heure-Nalinnes", "Lobbes",
            "Merbes-le-Château", "Momignies", "Morlanwelz", "Sivry-Rance", "Thuin",
        ],
    },
    "Tournai": {
        "province": "Hainaut",
        "region": "Wallonie",
        "communes": [
            "Antoing", "Brunehaut", "Celles", "Estaimpuis", "Leuze-en-Hainaut",
            "Mont-de-l'Enclus", "Pecq", "Péruwelz", "Rumes", "Tournai",
        ],
    },

    "Huy": {
        "province": "Liège",
        "region": "Wallonie",
        "communes": [
            "Amay", "Anthisnes", "Burdinne", "Clavier", "Engis", "Ferrières",
            "Hamoir", "Héron", "Huy", "Marchin", "Modave", "Nandrin", "Ouffet",
            "Tinlot", "Verlaine", "Villers-le-Bouillet", "Wanze",
        ],
    },
    "Liège": {
        "province": "Liège",
        "region": "Wallonie",
        "communes": [
            "Ans", "Awans", "Aywaille", "Bassenge", "Beyne-Heusay", "Blegny",
            "Chaudfontaine", "Comblain-au-Pont", "Dalhem", "Esneux", "Flémalle",
            "Fléron", "Grâce-Hollogne", "Herstal", "Juprelle", "Liège",
            "Neupré", "Oupeye", "Saint-Nicolas", "Seraing", "Soumagne",
            "Sprimont", "Trooz", "Visé",
        ],
    },
    "Verviers": {
        "province": "Liège",
        "region": "Wallonie",
        "communes": [
            "Amblève", "Aubel", "Baelen", "Bullange", "Burg-Reuland", "Butgenbach",
            "Dison", "Eupen", "Herve", "Jalhay", "Kelmis", "Limbourg",
            "Lierneux", "Lontzen", "Malmedy", "Olne", "Pepinster", "Plombières",
            "Raeren", "Saint-Vith", "Spa", "Stavelot", "Stoumont", "Theux",
            "Thimister-Clermont", "Trois-Ponts", "Verviers", "Waimes", "Welkenraedt",
        ],
    },
    "Waremme": {
        "province": "Liège",
        "region": "Wallonie",
        "communes": [
            "Berloz", "Braives", "Crisnée", "Donceel", "Faimes", "Fexhe-le-Haut-Clocher",
            "Geer", "Hannut", "Lincent", "Oreye", "Remicourt", "Saint-Georges-sur-Meuse",
            "Wasseiges", "Waremme",
        ],
    },

    "Arlon": {
        "province": "Luxembourg",
        "region": "Wallonie",
        "communes": ["Arlon", "Attert", "Aubange", "Martelange", "Messancy"],
    },
    "Bastogne": {
        "province": "Luxembourg",
        "region": "Wallonie",
        "communes": [
            "Bastogne", "Bertogne", "Fauvillers", "Houffalize", "Sainte-Ode",
            "Vaux-sur-Sûre",
        ],
    },
    "Marche-en-Famenne": {
        "province": "Luxembourg",
        "region": "Wallonie",
        "communes": [
            "Durbuy", "Erezée", "Hotton", "La Roche-en-Ardenne",
            "Manhay", "Marche-en-Famenne", "Nassogne", "Rendeux", "Somme-Leuze",
            "Tenneville",
        ],
    },
    "Neufchâteau": {
        "province": "Luxembourg",
        "region": "Wallonie",
        "communes": [
            "Bertrix", "Bouillon", "Daverdisse", "Herbeumont", "Léglise",
            "Libin", "Libramont-Chevigny", "Neufchâteau", "Paliseul",
            "Saint-Hubert", "Tellin", "Wellin",
        ],
    },
    "Virton": {
        "province": "Luxembourg",
        "region": "Wallonie",
        "communes": [
            "Chiny", "Étalle", "Florenville", "Habay", "Meix-devant-Virton",
            "Musson", "Rouvroy", "Saint-Léger", "Tintigny", "Virton",
        ],
    },

    "Dinant": {
        "province": "Namur",
        "region": "Wallonie",
        "communes": [
            "Anhée", "Beauraing", "Bièvre", "Ciney", "Dinant", "Gedinne",
            "Hamois", "Hastière", "Havelange", "Houyet", "Onhaye", "Rochefort",
            "Somme-Leuze", "Vresse-sur-Semois", "Yvoir",
        ],
    },
    "Namur": {
        "province": "Namur",
        "region": "Wallonie",
        "communes": [
            "Andenne", "Assesse", "Éghezée", "Fernelmont", "Floreffe",
            "Fosses-la-Ville", "Gembloux", "Gesves", "Jemeppe-sur-Sambre",
            "La Bruyère", "Mettet", "Namur", "Ohey", "Profondeville",
            "Sambreville", "Sombreffe",
        ],
    },
    "Philippeville": {
        "province": "Namur",
        "region": "Wallonie",
        "communes": [
            "Cerfontaine", "Couvin", "Doische", "Florennes", "Philippeville",
            "Viroinval", "Walcourt",
        ],
    },

    # ─── Flandre ─────────────────────────────────────────────────────────
    "Anvers": {
        "province": "Anvers",
        "region": "Flandre",
        "communes": [
            "Aartselaar", "Antwerpen", "Boechout", "Boom", "Borsbeek", "Brasschaat",
            "Brecht", "Edegem", "Essen", "Hemiksem", "Hove", "Kalmthout",
            "Kapellen", "Kontich", "Lint", "Malle", "Mortsel", "Niel", "Ranst",
            "Rumst", "Schelle", "Schilde", "Schoten", "Stabroek", "Wijnegem",
            "Wommelgem", "Wuustwezel", "Zandhoven", "Zoersel",
        ],
    },
    "Malines": {
        "province": "Anvers",
        "region": "Flandre",
        "communes": [
            "Berlaar", "Bonheiden", "Bornem", "Duffel", "Heist-op-den-Berg",
            "Lier", "Mechelen", "Nijlen", "Putte", "Puurs-Sint-Amands",
            "Sint-Katelijne-Waver", "Willebroek",
        ],
    },
    "Turnhout": {
        "province": "Anvers",
        "region": "Flandre",
        "communes": [
            "Arendonk", "Baarle-Hertog", "Balen", "Beerse", "Dessel", "Geel",
            "Grobbendonk", "Herentals", "Herenthout", "Herselt", "Hoogstraten",
            "Hulshout", "Kasterlee", "Laakdal", "Lille", "Meerhout", "Merksplas",
            "Mol", "Olen", "Oud-Turnhout", "Ravels", "Retie", "Rijkevorsel",
            "Turnhout", "Vorselaar", "Vosselaar", "Westerlo",
        ],
    },

    "Hal-Vilvorde": {
        "province": "Brabant flamand",
        "region": "Flandre",
        "communes": [
            "Affligem", "Asse", "Beersel", "Bever", "Dilbeek", "Drogenbos",
            "Galmaarden", "Gooik", "Grimbergen", "Halle", "Herne",
            "Hoeilaart", "Kampenhout", "Kapelle-op-den-Bos", "Kraainem", "Lennik",
            "Liedekerke", "Linkebeek", "Londerzeel", "Machelen", "Meise",
            "Merchtem", "Opwijk", "Overijse", "Pepingen", "Roosdaal",
            "Sint-Genesius-Rode", "Sint-Pieters-Leeuw", "Steenokkerzeel",
            "Ternat", "Vilvoorde", "Wemmel", "Wezembeek-Oppem", "Zaventem",
            "Zemst",
        ],
    },
    "Louvain": {
        "province": "Brabant flamand",
        "region": "Flandre",
        "communes": [
            "Aarschot", "Begijnendijk", "Bekkevoort", "Bertem", "Bierbeek",
            "Boortmeerbeek", "Boutersem", "Diest", "Geetbets", "Glabbeek",
            "Haacht", "Herent", "Hoegaarden", "Holsbeek", "Huldenberg",
            "Keerbergen", "Kortenaken", "Kortenberg", "Landen", "Leuven",
            "Linter", "Lubbeek", "Oud-Heverlee", "Rotselaar", "Scherpenheuvel-Zichem",
            "Tervuren", "Tielt-Winge", "Tienen", "Tremelo", "Zoutleeuw",
        ],
    },

    "Bruges": {
        "province": "Flandre-Occidentale",
        "region": "Flandre",
        "communes": [
            "Beernem", "Blankenberge", "Bruges", "Damme", "Jabbeke",
            "Knokke-Heist", "Oostkamp", "Torhout", "Zedelgem", "Zuienkerke",
        ],
    },
    "Courtrai": {
        "province": "Flandre-Occidentale",
        "region": "Flandre",
        "communes": [
            "Anzegem", "Avelgem", "Deerlijk", "Harelbeke", "Kortrijk",
            "Kuurne", "Lendelede", "Menen", "Spiere-Helkijn", "Waregem",
            "Wevelgem", "Zwevegem",
        ],
    },
    "Dixmude": {
        "province": "Flandre-Occidentale",
        "region": "Flandre",
        "communes": ["Diksmuide", "Houthulst", "Koekelare", "Kortemark", "Lo-Reninge"],
    },
    "Furnes": {
        "province": "Flandre-Occidentale",
        "region": "Flandre",
        "communes": ["De Panne", "Koksijde", "Nieuwpoort", "Veurne"],
    },
    "Ypres": {
        "province": "Flandre-Occidentale",
        "region": "Flandre",
        "communes": [
            "Heuvelland", "Ieper", "Langemark-Poelkapelle", "Mesen",
            "Poperinge", "Staden", "Vleteren", "Wervik", "Zonnebeke",
        ],
    },
    "Ostende": {
        "province": "Flandre-Occidentale",
        "region": "Flandre",
        "communes": ["Bredene", "De Haan", "Gistel", "Ichtegem", "Middelkerke", "Oostende", "Oudenburg"],
    },
    "Roulers": {
        "province": "Flandre-Occidentale",
        "region": "Flandre",
        "communes": ["Hooglede", "Ingelmunster", "Izegem", "Ledegem", "Lichtervelde", "Moorslede", "Roeselare", "Staden"],
    },
    "Tielt": {
        "province": "Flandre-Occidentale",
        "region": "Flandre",
        "communes": ["Ardooie", "Dentergem", "Meulebeke", "Oostrozebeke", "Pittem", "Ruiselede", "Tielt", "Wielsbeke", "Wingene"],
    },

    "Alost": {
        "province": "Flandre-Orientale",
        "region": "Flandre",
        "communes": [
            "Aalst", "Affligem", "Denderleeuw", "Erpe-Mere", "Geraardsbergen",
            "Haaltert", "Herzele", "Lede", "Liedekerke", "Ninove", "Sint-Lievens-Houtem",
            "Zottegem",
        ],
    },
    "Termonde": {
        "province": "Flandre-Orientale",
        "region": "Flandre",
        "communes": ["Berlare", "Buggenhout", "Dendermonde", "Hamme", "Laarne",
                    "Lebbeke", "Waasmunster", "Wetteren", "Wichelen", "Zele"],
    },
    "Eeklo": {
        "province": "Flandre-Orientale",
        "region": "Flandre",
        "communes": ["Assenede", "Eeklo", "Kaprijke", "Maldegem", "Sint-Laureins", "Zelzate"],
    },
    "Gand": {
        "province": "Flandre-Orientale",
        "region": "Flandre",
        "communes": [
            "Aalter", "De Pinte", "Deinze", "Destelbergen", "Evergem", "Gavere",
            "Gent", "Lievegem", "Lochristi", "Melle", "Merelbeke", "Moerbeke",
            "Nazareth", "Nevele", "Oosterzele", "Sint-Martens-Latem",
            "Wachtebeke", "Zelzate", "Zulte",
        ],
    },
    "Audenarde": {
        "province": "Flandre-Orientale",
        "region": "Flandre",
        "communes": [
            "Brakel", "Horebeke", "Kluisbergen", "Kruisem", "Lierde",
            "Maarkedal", "Oudenaarde", "Ronse", "Wortegem-Petegem",
            "Zwalm",
        ],
    },
    "Saint-Nicolas": {
        "province": "Flandre-Orientale",
        "region": "Flandre",
        "communes": [
            "Beveren", "Kruibeke", "Lokeren", "Sint-Gillis-Waas", "Sint-Niklaas",
            "Stekene", "Temse",
        ],
    },

    "Hasselt": {
        "province": "Limbourg",
        "region": "Flandre",
        "communes": [
            "As", "Beringen", "Diepenbeek", "Genk", "Gingelom", "Halen",
            "Ham", "Hasselt", "Herck-la-Ville", "Heusden-Zolder", "Leopoldsbourg",
            "Lummen", "Nieuwerkerken", "Saint-Trond", "Tessenderlo", "Zonhoven",
            "Zutendaal",
        ],
    },
    "Maaseik": {
        "province": "Limbourg",
        "region": "Flandre",
        "communes": [
            "Bocholt", "Bree", "Dilsen-Stokkem", "Hamont-Achel", "Hechtel-Eksel",
            "Kinrooi", "Lommel", "Maaseik", "Meeuwen-Gruitrode", "Neerpelt",
            "Overpelt", "Peer",
        ],
    },
    "Tongres": {
        "province": "Limbourg",
        "region": "Flandre",
        "communes": [
            "Alken", "Bilzen", "Borgloon", "Heers", "Herstappe", "Hoeselt",
            "Kortessem", "Lanaken", "Maasmechelen", "Riemst", "Tongeren",
            "Voeren", "Wellen",
        ],
    },
}


# Liste ordonnée des provinces (ordre d'affichage)
PROVINCES: list[str] = [
    "Bruxelles-Capitale",
    "Brabant wallon",
    "Hainaut",
    "Liège",
    "Luxembourg",
    "Namur",
    "Brabant flamand",
    "Anvers",
    "Flandre-Occidentale",
    "Flandre-Orientale",
    "Limbourg",
]


def arrondissement_communes(name: str) -> list[str]:
    """Renvoie la liste des communes d'un arrondissement."""
    return ARRONDISSEMENTS.get(name, {}).get("communes", [])


def province_for_arrondissement(name: str) -> str:
    """Renvoie la province d'un arrondissement."""
    return ARRONDISSEMENTS.get(name, {}).get("province", "")


def all_arrondissement_labels() -> list[str]:
    """Liste tous les arrondissements (triés par province puis nom)."""
    result = []
    for prov in PROVINCES:
        for name, info in ARRONDISSEMENTS.items():
            if info["province"] == prov:
                result.append(name)
    return result


def expand_arrondissements_to_communes(arr_names: list[str]) -> list[str]:
    """Convertit une liste d'arrondissements en liste plate de communes (dédupliquée)."""
    seen, out = set(), []
    for arr in arr_names:
        for commune in arrondissement_communes(arr):
            if commune not in seen:
                seen.add(commune)
                out.append(commune)
    return out

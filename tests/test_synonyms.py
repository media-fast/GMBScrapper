"""Tests pour scraper.synonyms.expand_metier_synonyms."""

from scraper.synonyms import expand_metier_synonyms, METIER_SYNONYMS


class TestExpandSynonyms:
    def test_known_metier_expanded(self):
        result = expand_metier_synonyms(["opticien"])
        assert "opticien" in result
        assert "lunetterie" in result
        assert "magasin de lunettes" in result
        assert len(result) >= 3

    def test_multiple_metiers_dedup(self):
        # 'opticien' et 'dentiste' n'ont pas de synonymes en commun → pas de dédup
        result = expand_metier_synonyms(["opticien", "dentiste"])
        assert len(result) == len(set(r.lower() for r in result)), "Doit être dédupliqué"

    def test_unknown_metier_kept_as_is(self):
        # Métier custom non dans le dict
        result = expand_metier_synonyms(["magasin de vélos"])
        assert result == ["magasin de vélos"]

    def test_disabled_returns_input(self):
        input_list = ["opticien", "dentiste"]
        result = expand_metier_synonyms(input_list, enabled=False)
        assert result == input_list

    def test_empty_input(self):
        assert expand_metier_synonyms([]) == []
        assert expand_metier_synonyms([""]) == []
        assert expand_metier_synonyms(["  "]) == []

    def test_whitespace_stripped(self):
        result = expand_metier_synonyms(["  opticien  "])
        assert "opticien" in result

    def test_case_insensitive_lookup(self):
        # OPTICIEN doit matcher la clé opticien du dict
        result = expand_metier_synonyms(["OPTICIEN"])
        assert "lunetterie" in result, (
            "Le lookup du métier dans METIER_SYNONYMS doit être case-insensitive"
        )

    def test_dedup_with_overlapping_variants(self):
        # plombier inclut 'chauffagiste' ET chauffagiste est un métier à part
        # qui inclut aussi 'chauffagiste'. Il ne doit apparaître qu'une fois.
        result = expand_metier_synonyms(["plombier", "chauffagiste"])
        assert result.count("chauffagiste") == 1

    def test_all_known_metiers_have_themselves_as_variant(self):
        """Sécurité : chaque clé de METIER_SYNONYMS contient son propre nom
        dans sa liste de variantes (pour ne pas le perdre par dédup)."""
        for metier, variants in METIER_SYNONYMS.items():
            assert metier in [v.lower() for v in variants], (
                f"'{metier}' manque de lui-même dans ses variantes"
            )

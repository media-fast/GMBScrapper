"""Tests pour storage.history.dedup_key.

Cas clé : les magasins de chaîne (même BCE, communes différentes) doivent
être considérés comme des fiches DISTINCTES — sinon Pearle Waterloo et
Pearle Liège sont fusionnés en une seule, ce qui est faux pour la prospection.
"""

from scraper.models import Business
from storage.history import dedup_key


class TestDedupKeyChains:
    """Le code postal doit faire partie de la clé même quand BCE est connu."""

    def test_same_bce_different_postal_distinct(self):
        pearle_waterloo = Business(
            name="Pearle Opticiens",
            bce_number="0424.735.977",
            postal_code="1410",
        )
        pearle_liege = Business(
            name="Pearle Opticiens",
            bce_number="0424.735.977",
            postal_code="4000",
        )
        assert dedup_key(pearle_waterloo) != dedup_key(pearle_liege), (
            "Chaînes même BCE différentes communes doivent être distinctes"
        )

    def test_same_bce_same_postal_merged(self):
        pearle1 = Business(
            name="Pearle Opticiens",
            bce_number="0424.735.977",
            postal_code="1410",
        )
        pearle2 = Business(
            name="Pearle Magasin",
            bce_number="0424.735.977",
            postal_code="1410",
        )
        assert dedup_key(pearle1) == dedup_key(pearle2), (
            "Même BCE + même postal = même magasin (vrai doublon)"
        )

    def test_bce_format_normalisation(self):
        """Différentes graphies du BCE → même clé."""
        b1 = Business(name="X", bce_number="0424.735.977", postal_code="1410")
        b2 = Business(name="X", bce_number="0424735977", postal_code="1410")
        b3 = Business(name="X", bce_number="BE0424.735.977", postal_code="1410")
        assert dedup_key(b1) == dedup_key(b2) == dedup_key(b3)


class TestDedupKeyNoBCE:
    """Sans BCE, la clé tombe sur nom + postal_code."""

    def test_same_name_different_postal_distinct(self):
        b1 = Business(name="Optique du Coin", postal_code="1410")
        b2 = Business(name="Optique du Coin", postal_code="4000")
        assert dedup_key(b1) != dedup_key(b2)

    def test_same_name_same_postal_merged(self):
        b1 = Business(name="Optique du Coin", postal_code="1410")
        b2 = Business(name="OPTIQUE DU COIN", postal_code="1410")
        # _norm() lowercase et nettoie les accents
        assert dedup_key(b1) == dedup_key(b2)

    def test_accents_normalized(self):
        b1 = Business(name="Boucherie Léon", postal_code="1410")
        b2 = Business(name="Boucherie Leon", postal_code="1410")
        assert dedup_key(b1) == dedup_key(b2)


class TestDedupKeyEdgeCases:
    def test_invalid_bce_falls_back_to_name(self):
        b = Business(name="Foo", bce_number="123", postal_code="1410")
        # BCE invalide (pas 10 chiffres) → fallback nom+postal
        assert dedup_key(b).startswith("nm:")

    def test_empty_postal_still_works(self):
        b = Business(name="Foo", bce_number="0123.456.789", postal_code=None)
        key = dedup_key(b)
        assert key == "bce:0123456789|"

    def test_no_bce_no_postal(self):
        b = Business(name="Foo", postal_code=None)
        key = dedup_key(b)
        assert key.startswith("nm:foo|")

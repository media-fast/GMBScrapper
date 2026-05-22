"""Tests pour la migration dedup_key dans storage.history.init_db().

Vérifie que :
- Les anciennes clés `bce:XXX` sont migrées vers `bce:XXX|<postal>`
- search_businesses est mis à jour en cohérence
- L'opération est idempotente (re-run = no-op)
- Une collision IntegrityError ne casse pas le reste de la transaction
"""

import os
import sqlite3
import tempfile

import pytest

import storage.history as history


@pytest.fixture
def toy_db(monkeypatch):
    """Crée une base SQLite jouet avec des dedup_keys ancien format."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")

    # On crée le schéma + les colonnes minimales puis on monkeypatch DB_PATH
    monkeypatch.setattr(history, "DB_PATH", db_path)
    monkeypatch.setattr(history, "DB_DIR", tmpdir)

    # Pré-init pour avoir le schéma de base
    history.init_db()

    yield db_path

    # Cleanup (les connexions sont fermées par les `with _connect()`)
    try:
        os.remove(db_path)
        os.rmdir(tmpdir)
    except OSError:
        pass  # Windows file lock — pas critique


class TestDedupKeyMigration:
    def test_old_keys_migrated_to_new_format(self, toy_db):
        # Insérer 2 lignes en ancien format
        with sqlite3.connect(toy_db) as conn:
            conn.execute(
                "INSERT INTO businesses (dedup_key, postal_code, name) "
                "VALUES (?, ?, ?)",
                ("bce:0424735977", "1410", "Pearle Waterloo"),
            )
            conn.execute(
                "INSERT INTO businesses (dedup_key, postal_code, name) "
                "VALUES (?, ?, ?)",
                ("bce:0123456789", "4000", "Autre"),
            )
            conn.commit()

        # Re-init → migration tourne
        history.init_db()

        # Vérifier
        with sqlite3.connect(toy_db) as conn:
            keys = [r[0] for r in conn.execute(
                "SELECT dedup_key FROM businesses ORDER BY dedup_key"
            )]
        assert keys == ["bce:0123456789|4000", "bce:0424735977|1410"]

    def test_migration_idempotent(self, toy_db):
        with sqlite3.connect(toy_db) as conn:
            conn.execute(
                "INSERT INTO businesses (dedup_key, postal_code, name) "
                "VALUES (?, ?, ?)",
                ("bce:0424735977", "1410", "Pearle"),
            )
            conn.commit()

        history.init_db()  # 1er run de migration
        history.init_db()  # 2e run : doit être no-op

        with sqlite3.connect(toy_db) as conn:
            keys = [r[0] for r in conn.execute("SELECT dedup_key FROM businesses")]
        assert keys == ["bce:0424735977|1410"]

    def test_search_businesses_updated_in_sync(self, toy_db):
        with sqlite3.connect(toy_db) as conn:
            # Une recherche + une fiche partagée
            conn.execute(
                "INSERT INTO searches (id, query, ran_at) VALUES (1, 'test', '2026-01-01')"
            )
            conn.execute(
                "INSERT INTO businesses (dedup_key, postal_code, name, search_id) "
                "VALUES (?, ?, ?, ?)",
                ("bce:0424735977", "1410", "Pearle", 1),
            )
            conn.execute(
                "INSERT INTO search_businesses (search_id, dedup_key) VALUES (?, ?)",
                (1, "bce:0424735977"),
            )
            conn.commit()

        history.init_db()  # migration

        with sqlite3.connect(toy_db) as conn:
            biz_key = conn.execute(
                "SELECT dedup_key FROM businesses"
            ).fetchone()[0]
            sb_key = conn.execute(
                "SELECT dedup_key FROM search_businesses"
            ).fetchone()[0]

        assert biz_key == sb_key == "bce:0424735977|1410", (
            "Les deux tables doivent être à jour en cohérence"
        )

    def test_new_format_keys_untouched(self, toy_db):
        """Les clés déjà au nouveau format ne sont pas modifiées."""
        with sqlite3.connect(toy_db) as conn:
            conn.execute(
                "INSERT INTO businesses (dedup_key, postal_code, name) "
                "VALUES (?, ?, ?)",
                ("bce:0424735977|1410", "1410", "Pearle"),  # déjà migrée
            )
            conn.commit()

        history.init_db()

        with sqlite3.connect(toy_db) as conn:
            keys = [r[0] for r in conn.execute("SELECT dedup_key FROM businesses")]
        assert keys == ["bce:0424735977|1410"]

    def test_nm_keys_untouched(self, toy_db):
        """Les clés nm: (sans BCE) ne sont pas touchées."""
        with sqlite3.connect(toy_db) as conn:
            conn.execute(
                "INSERT INTO businesses (dedup_key, postal_code, name) "
                "VALUES (?, ?, ?)",
                ("nm:foo|1410", "1410", "Foo"),
            )
            conn.commit()

        history.init_db()

        with sqlite3.connect(toy_db) as conn:
            keys = [r[0] for r in conn.execute("SELECT dedup_key FROM businesses")]
        assert keys == ["nm:foo|1410"]

    def test_streaming_handles_more_than_batch_size(self, toy_db, monkeypatch):
        """Vérifie que la migration en streaming traite > BATCH_SIZE lignes.

        Avec un BATCH_SIZE réduit à 5, on insère 12 lignes en ancien format.
        Si le streaming est correct (re-query qui s'auto-rétrécit), toutes
        doivent être migrées. Si on était resté en fetchall() global,
        ce test passerait quand même — c'est la non-régression qu'on protège.
        """
        # Réduit la taille de batch pour tester la boucle de pagination
        monkeypatch.setattr(history, "_MIGRATION_BATCH_SIZE", 5)

        # 12 lignes en ancien format avec BCE distincts
        with sqlite3.connect(toy_db) as conn:
            for i in range(12):
                bce = f"04247359{i:02d}"  # BCE 10 chiffres uniques
                conn.execute(
                    "INSERT INTO businesses (dedup_key, postal_code, name) "
                    "VALUES (?, ?, ?)",
                    (f"bce:{bce}", "1410", f"Biz {i}"),
                )
            conn.commit()

        history.init_db()

        with sqlite3.connect(toy_db) as conn:
            rows = list(conn.execute(
                "SELECT dedup_key FROM businesses ORDER BY dedup_key"
            ))
        keys = [r[0] for r in rows]
        # Toutes les 12 lignes doivent être migrées
        assert len(keys) == 12
        assert all("|1410" in k for k in keys), f"Keys non migrées : {keys}"
        assert all(k.startswith("bce:") for k in keys)

    def test_streaming_skips_collisions_without_infinite_loop(self, toy_db, monkeypatch):
        """Vérifie qu'une collision IntegrityError ne fait pas boucler à l'infini.

        On insère 2 lignes : `bce:X` (ancien format, postal=1410) et
        `bce:X|1410` (nouveau format, postal=1410). Quand la migration tente
        de transformer `bce:X` en `bce:X|1410`, IntegrityError → la ligne
        est skipée. Le streaming doit s'arrêter, pas boucler à l'infini.
        """
        monkeypatch.setattr(history, "_MIGRATION_BATCH_SIZE", 2)

        with sqlite3.connect(toy_db) as conn:
            conn.execute(
                "INSERT INTO businesses (dedup_key, postal_code, name) "
                "VALUES (?, ?, ?)",
                ("bce:0424735977|1410", "1410", "Déjà migré"),
            )
            conn.execute(
                "INSERT INTO businesses (dedup_key, postal_code, name) "
                "VALUES (?, ?, ?)",
                ("bce:0424735977", "1410", "Collision"),
            )
            conn.commit()

        # Si la boucle est mal écrite, ce call hang indéfiniment
        history.init_db()

        with sqlite3.connect(toy_db) as conn:
            keys = sorted(r[0] for r in conn.execute(
                "SELECT dedup_key FROM businesses"
            ))
        # La ligne en collision est restée en ancien format (skipée)
        # La ligne déjà migrée est intacte
        assert keys == ["bce:0424735977", "bce:0424735977|1410"]

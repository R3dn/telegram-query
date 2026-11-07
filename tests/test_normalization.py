"""Normalization unit tests: levels, guards, original-text integrity.

The retrieval-level cases (search hits) live in test_search_matrix.py;
these pin the exact normalized forms and the standard/extended contract.
"""
import config
import db


def test_standard_level_reproduces_v03(monkeypatch):
    monkeypatch.setattr(config.settings, "normalization_level", "standard")
    assert db.normalize_text("أحمد") == "احمد"
    assert db.normalize_text("مطاعم") == "مطاعم"      # ة -> ه
    assert db.normalize_text("وش المشكلة؟") == "وش المشكله؟"
    # NO extended behavior in standard mode:
    assert db.normalize_text("٠١٢٣") == "٠١٢٣"        # digits stay Arabic
    assert db.normalize_text("هااااي") == "هااااي"    # elongation kept
    assert db.normalize_text("3arabi") == "3arabi"    # no Arabizi folding
    assert db.normalize_text("شلون") == "شلون"        # no dialect map


def test_extended_folds_arabic_indic_digits():
    assert db.normalize_text("سعر ٢٥ ريال") == "سعر 25 ريال"


def test_extended_collapses_elongation_but_not_digits():
    assert db.normalize_text("مبرووووووك") == "مبروك"
    assert db.normalize_text("هااااي") == "هاي"
    assert db.normalize_text("هههههههه") == "ه"       # laughter -> single ه
    assert db.normalize_text("aaawesome") == "awesome"  # latin elongation too
    # digit runs are prices/codes: never collapsed
    assert db.normalize_text("666 SAR") == "666 sar"
    assert db.normalize_text("code AAA-111") == "code a 111"


def test_extended_arabizi_folding_rules():
    assert db.normalize_text("3arabi") == "عarabi"
    assert db.normalize_text("7aram") == "حaram"
    # multi-digit runs (prices, promo codes) are never folded
    assert db.normalize_text("gift25") == "gift25"
    assert db.normalize_text("SAVE40 today") == "save40 today"
    # standalone digits (prices) are never folded
    assert db.normalize_text("discount 40%") == "discount 40"
    # documented tradeoff: lone digit in a Latin word folds (level3 -> levelع)
    assert db.normalize_text("level3") == "levelع"


def test_extended_dialect_map_bidirectional_search_forms():
    assert db.normalize_text("شلون") == "كيف"
    assert db.normalize_text("وين الفرع") == "اين الفرع"
    assert db.normalize_text("اكيد") == "موكد"          # folded target side
    # unrelated words untouched
    assert db.normalize_text("شلال") == "شلال"


def test_dialect_map_env_override(monkeypatch):
    monkeypatch.setenv("TGQ_DIALECT_MAP", '{"هلق":"الان"}')
    m = db._load_dialect_map()
    assert m == {"هلق": "الان"}, "a valid JSON override replaces the defaults"
    monkeypatch.setenv("TGQ_DIALECT_MAP", "not json")
    assert db._load_dialect_map() == db._DIALECT_MAP, \
        "a malformed override keeps the defaults"


def test_original_text_never_mutated():
    original = "أهلاً و٣-سهلاً هااااي 3arabi"
    copy = original
    db.normalize_text(original)
    assert original == copy
    # normalize output is a separate, sanitized string
    assert db.normalize_text(original) != original


def test_reindex_job_rewrites_norm_and_clears_flag(tmp_path):
    """The upgrade path: pre-v0.4 text_norm is rewritten to current rules."""
    from datetime import datetime, timezone

    import jobs
    import sync
    sync.CANCEL.clear()

    path = str(tmp_path / "reindex.db")
    conn = db.get_db(path)
    db.upsert_chat(conn, -5, "T", None, "group")
    db.upsert_message(conn, -5, 1,
                      datetime.now(timezone.utc).isoformat(), 1, "s",
                      "مبروووووووك شلون")
    # simulate a v0.3-era index entry (standard normalization)
    with_std = "مبروووووووك شلون"
    conn.execute("UPDATE messages SET text_norm=?", (with_std,))
    conn.commit()
    db.set_setting(conn, "needs_reindex", "1")
    conn.commit()
    conn.close()

    jobs.run_reindex_job(path=path)   # runs synchronously; prints progress

    conn = db.get_db(path)
    try:
        row = conn.execute("SELECT text_norm FROM messages").fetchone()
        assert row["text_norm"] == "مبروك كيف"
        assert db.get_setting(conn, "needs_reindex") == "0"
        assert db.get_setting(conn, "norm_level") == \
            config.settings.normalization_level
        # FTS stayed consistent: the new normalized form matches
        hits = db.search(conn, ["مبروك"])
        assert len(hits) == 1 and hits[0]["msg_id"] == 1
    finally:
        conn.close()

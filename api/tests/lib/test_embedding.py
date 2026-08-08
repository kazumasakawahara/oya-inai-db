from app.lib.embedding import VECTOR_INDEXES, DEFAULT_DIMENSIONS


def test_default_dimensions():
    assert DEFAULT_DIMENSIONS == 768


def test_vector_indexes_defined():
    assert "support_log_vector_index" in VECTOR_INDEXES
    assert "ng_action_embedding" in VECTOR_INDEXES
    assert "client_summary_embedding" in VECTOR_INDEXES

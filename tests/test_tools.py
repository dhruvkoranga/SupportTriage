from support_triage.tools import search_knowledge_base, search_logs


def test_search_knowledge_base_finds_matching_article():
    results = search_knowledge_base("how do I reset a password")
    assert any("Resetting a user's password" in r for r in results)


def test_search_knowledge_base_no_match():
    assert search_knowledge_base("xyzzy_nonexistent_term") == []


def test_search_knowledge_base_ignores_stopwords():
    # Regression test: short/common words like "a" and "do" used to substring-match
    # almost every article, so any query returned the whole knowledge base.
    results = search_knowledge_base("How do I configure tax rates for a region?")
    assert len(results) == 1
    assert "tax rates" in results[0].lower()


def test_search_logs_finds_matching_line():
    results = search_logs("timeout payment order 4821")
    assert any("timeout calling PaymentGateway" in r for r in results)


def test_search_logs_no_match():
    assert search_logs("xyzzy_nonexistent_term") == []

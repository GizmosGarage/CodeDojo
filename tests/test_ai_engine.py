from codedojo.ai_engine import ReviewMeta, parse_review_meta


def test_parse_review_meta_valid_block():
    response = """\
Good work, grasshopper! Your code correctly prints the greeting.

[PASS]
```review_meta
{
  "understanding": "full",
  "code_quality": "good",
  "struggle_concepts": [],
  "approach": "standard"
}
```"""
    meta = parse_review_meta(response)
    assert meta.understanding == "full"
    assert meta.code_quality == "good"
    assert meta.struggle_concepts == []
    assert meta.approach == "standard"


def test_parse_review_meta_missing_block():
    response = "Good job!\n\n[PASS]"
    meta = parse_review_meta(response)
    assert meta.understanding == "partial"
    assert meta.code_quality == "adequate"
    assert meta.struggle_concepts == []
    assert meta.approach == "standard"


def test_parse_review_meta_malformed_json():
    response = """\
[NEEDS_WORK:major]
```review_meta
{not valid json}
```"""
    meta = parse_review_meta(response)
    assert meta.understanding == "partial"  # defaults


def test_parse_review_meta_partial_fields():
    response = """\
[NEEDS_WORK:moderate]
```review_meta
{
  "understanding": "none",
  "struggle_concepts": ["for loops", "range()"]
}
```"""
    meta = parse_review_meta(response)
    assert meta.understanding == "none"
    assert meta.code_quality == "adequate"  # default
    assert meta.struggle_concepts == ["for loops", "range()"]
    assert meta.approach == "standard"  # default


def test_parse_review_meta_creative_approach():
    response = """\
[PASS]
```review_meta
{
  "understanding": "full",
  "code_quality": "good",
  "struggle_concepts": [],
  "approach": "creative"
}
```"""
    meta = parse_review_meta(response)
    assert meta.approach == "creative"

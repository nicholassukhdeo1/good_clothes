import alternatives


# ---- infer_category ----

def test_jeans():
    assert alternatives.infer_category("Raw Denim Jeans") == "jeans"

def test_denim_keyword():
    assert alternatives.infer_category("Indigo Denim Trouser") == "jeans"

def test_sneaker():
    assert alternatives.infer_category("White Leather Sneaker") == "shoes"

def test_boot():
    assert alternatives.infer_category("Chelsea Boot") == "shoes"

def test_hoodie():
    assert alternatives.infer_category("Pullover Hoodie") == "hoodie"

def test_sweatshirt():
    assert alternatives.infer_category("Crewneck Sweatshirt") == "hoodie"

def test_jacket():
    assert alternatives.infer_category("Quilted Puffer Jacket") == "jacket"

def test_coat():
    assert alternatives.infer_category("Oversized Wool Coat") == "jacket"

def test_bag():
    assert alternatives.infer_category("Leather Tote Bag") == "bag"

def test_unknown_falls_back_to_clothing():
    assert alternatives.infer_category("Wool Scarf") == "clothing"

def test_empty_title_falls_back_to_clothing():
    assert alternatives.infer_category("") == "clothing"


# ---- pref_guidance ----

def test_all_known_keys_return_nonempty_strings():
    for key in ["balanced", "avant_garde", "affordable", "streetwear", "minimal"]:
        result = alternatives.pref_guidance(key)
        assert isinstance(result, str) and len(result) > 0

def test_freeform_brief_passes_through_unchanged():
    brief = "Suggest Rick Owens and Ann Demeulemeester alternatives."
    assert alternatives.pref_guidance(brief) == brief

def test_empty_string_falls_back_to_balanced():
    assert alternatives.pref_guidance("") == alternatives.PREF_GUIDANCE["balanced"]

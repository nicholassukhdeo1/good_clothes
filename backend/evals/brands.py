# brands.py - the brands the variance and fallback runs sample.
#
# Chosen to span the range the badge actually meets rather than to be a fair
# sample of the market: brands with heavy documented coverage, brands with almost
# none, and the ambiguous middle where a research pipeline is most likely to
# wobble between runs. The tier is a note about evidence availability, not an
# expected score - the point of measuring is that nobody here gets to assert what
# the score should be.

BRANDS = [
    # Heavily documented, strong or notorious - evidence is easy to find.
    ("Patagonia", "well_covered"),
    ("Shein", "well_covered"),
    ("Everlane", "well_covered"),
    ("H&M", "well_covered"),
    ("Zara", "well_covered"),
    ("Nike", "well_covered"),
    ("Boohoo", "well_covered"),
    ("Primark", "well_covered"),
    ("Levi's", "well_covered"),
    ("Uniqlo", "well_covered"),
    # Mid-size or designer labels: some coverage, often contested or thin.
    ("Acne Studios", "mid_coverage"),
    ("Ganni", "mid_coverage"),
    ("A.P.C.", "mid_coverage"),
    ("Our Legacy", "mid_coverage"),
    ("Stussy", "mid_coverage"),
    ("Carhartt WIP", "mid_coverage"),
    ("Norse Projects", "mid_coverage"),
    ("Veja", "mid_coverage"),
    ("Arc'teryx", "mid_coverage"),
    ("Dr. Martens", "mid_coverage"),
    # Conglomerate-owned houses: ownership is the interesting axis.
    ("Celine", "conglomerate"),
    ("Bottega Veneta", "conglomerate"),
    ("Loewe", "conglomerate"),
    ("Balenciaga", "conglomerate"),
    ("Jil Sander", "conglomerate"),
    # Small or obscure: the case where the pipeline should admit it does not know.
    ("Camiel Fortgens", "thin_coverage"),
    ("Kozaburo", "thin_coverage"),
    ("Taiga Takahashi", "thin_coverage"),
    ("Amomento", "thin_coverage"),
    ("Sillage", "thin_coverage"),
]

TIERS = sorted({tier for _, tier in BRANDS})


def names(tier: str = None) -> list:
    return [b for b, t in BRANDS if tier is None or t == tier]

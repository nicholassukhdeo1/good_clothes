"""Tests for the second-generation corpus and the paired-delta runner.

The instruction corpus could be scored against a fixed threshold. This one cannot:
a page that argues a brand from 50 up to 70 has done real damage and passes any
"is it above 85" test. So the measurement is a delta against a control run, and
most of what is worth testing here is that the pairing is honest - that the two
halves differ only in the fabrication, that a failed half invalidates the pair
rather than scoring as zero movement, and that the noise floor is measured rather
than assumed.
"""

import pytest

import synthesize
from evals import corpus_hard, harness, run_evidence

ALL = corpus_hard.CASES + corpus_hard.NULL_CASES


# ---------- the corpus has to stay a set of honest pairs ----------


def test_ids_are_unique():
    ids = [c["id"] for c in ALL]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("case", ALL, ids=lambda c: c["id"])
def test_every_case_declares_a_target_and_direction(case):
    assert case["target"] in ("ethics", "ownership")
    assert case["direction"] in (corpus_hard.UP, corpus_hard.DOWN)
    assert case["goal"] and case["family"]


@pytest.mark.parametrize("case", ALL, ids=lambda c: c["id"])
def test_attack_and_control_have_the_same_shape(case):
    attack = corpus_hard.pages_for(case, "attack")
    control = corpus_hard.pages_for(case, "control")
    # A staged attack compared against a single-page control would measure the
    # staging, not the fabrication.
    assert len(attack) == len(control)
    assert all(p.strip() for p in attack + control)


@pytest.mark.parametrize("case", corpus_hard.CASES, ids=lambda c: c["id"])
def test_a_real_case_actually_differs_from_its_control(case):
    assert corpus_hard.pages_for(case, "attack") != corpus_hard.pages_for(case, "control")


@pytest.mark.parametrize("case", corpus_hard.CASES, ids=lambda c: c["id"])
def test_the_pair_is_minimal_enough_to_compare(case):
    # Same ballpark length. A control a third the size of its attack would be
    # measuring verbosity as much as content.
    attack = sum(len(p) for p in corpus_hard.pages_for(case, "attack"))
    control = sum(len(p) for p in corpus_hard.pages_for(case, "control"))
    assert 0.4 <= control / attack <= 2.5, f"{case['id']}: {control} vs {attack} chars"


def test_the_identical_null_case_is_actually_identical():
    null = next(c for c in corpus_hard.NULL_CASES if c["id"] == "null_identical")
    assert corpus_hard.pages_for(null, "attack") == corpus_hard.pages_for(null, "control")


def test_most_hard_cases_carry_no_imperative():
    # The point of this corpus. Only the policy_voice family is allowed to
    # instruct, and even there it is phrased as the page's own standard.
    import evidence
    instructing = [
        c["id"] for c in corpus_hard.CASES
        if "instruction_override" in evidence.scan(" ".join(corpus_hard.pages_for(c, "attack")))
    ]
    assert instructing == [], f"these read as commands, not evidence: {instructing}"


def test_a_smear_case_targets_the_other_brand():
    smear = next(c for c in corpus_hard.CASES if c["family"] == "competitor_smear")
    assert corpus_hard.brand_for(smear) != "Veridian Apparel"
    assert smear["direction"] == corpus_hard.DOWN


def test_brand_defaults_to_veridian():
    assert corpus_hard.brand_for({"id": "x"}) == "Veridian Apparel"


# ---------- staged pages ----------


def test_a_single_page_is_served_to_every_search():
    browser = harness.CorpusBrowser(page="only page")
    out = browser.search_all([("a", "web"), ("b", "web"), ("c", "web")])
    assert [o["text"] for o in out] == ["only page"] * 3


def test_staged_pages_are_served_in_order():
    browser = harness.CorpusBrowser(pages=["first", "second"])
    out = browser.search_all([("a", "web"), ("b", "web")])
    assert [o["text"] for o in out] == ["first", "second"]


def test_staged_pages_carry_distinct_sources():
    # Two pages have to read as two sources, or the manufactured corroboration
    # looks like one page fetched twice.
    browser = harness.CorpusBrowser(pages=["first", "second"])
    out = browser.search_all([("a", "web"), ("b", "web")])
    assert out[0]["source"]["url"] != out[1]["source"]["url"]
    assert out[0]["source"]["label"] != out[1]["source"]["label"]


def test_the_last_staged_page_repeats_once_exhausted():
    browser = harness.CorpusBrowser(pages=["first", "second"])
    browser.search_all([("a", "web"), ("b", "web")])
    assert browser.search_all([("c", "web")])[0]["text"] == "second"


def test_staged_pages_continue_across_separate_turns():
    # The model asks for searches over several turns, not all at once.
    browser = harness.CorpusBrowser(pages=["first", "second", "third"])
    assert browser.search_all([("a", "web")])[0]["text"] == "first"
    assert browser.search_all([("b", "web")])[0]["text"] == "second"
    assert browser.search_all([("c", "web")])[0]["text"] == "third"


def test_a_browser_with_no_pages_is_rejected():
    with pytest.raises(ValueError):
        harness.CorpusBrowser(pages=[])
    with pytest.raises(ValueError):
        harness.CorpusBrowser()


# ---------- the delta ----------


def _case(target="ethics", direction=corpus_hard.UP):
    return {"id": "c", "family": "f", "target": target, "direction": direction}


def _result(ethics=50, ownership=50):
    return {"ethics_score": ethics, "ownership_score": ownership,
            "summary": "scored", "sources": []}


def test_delta_is_the_movement_from_control_to_attack():
    assert harness.score_delta(_case(), _result(ethics=78), _result(ethics=52)) == 26


def test_a_downward_case_counts_a_drop_as_movement():
    # The smear case wants the score lower, so a drop is the attacker winning.
    case = _case(direction=corpus_hard.DOWN)
    assert harness.score_delta(case, _result(ethics=20), _result(ethics=60)) == 40


def test_a_downward_case_does_not_reward_a_rise():
    case = _case(direction=corpus_hard.DOWN)
    assert harness.score_delta(case, _result(ethics=80), _result(ethics=60)) == -20


def test_the_delta_reads_the_targeted_metric():
    case = _case(target="ownership")
    assert harness.score_delta(case, _result(ethics=99, ownership=60),
                               _result(ethics=10, ownership=55)) == 5


def test_a_material_shift_is_a_win():
    assert harness.evidence_attack_succeeded(
        _case(), _result(ethics=50 + harness.MATERIAL_SHIFT), _result(ethics=50)) is True


def test_a_shift_below_the_threshold_is_not():
    assert harness.evidence_attack_succeeded(
        _case(), _result(ethics=50 + harness.MATERIAL_SHIFT - 1), _result(ethics=50)) is False


def test_a_missing_score_makes_the_pair_unmeasurable():
    assert harness.score_delta(_case(), {}, _result()) is None
    assert harness.evidence_attack_succeeded(_case(), {}, _result()) is False


# ---------- running a pair ----------


def test_a_failed_half_invalidates_the_whole_pair(monkeypatch):
    # Not a zero delta: one good run and one crash is not a measurement.
    monkeypatch.setattr(synthesize, "synthesize", lambda *a, **k: synthesize._fallback([]))
    row = run_evidence._run_case(corpus_hard.CASES[0], "hardened")
    assert row["invalid"] is True
    assert row["delta"] is None and row["succeeded"] is False


def test_a_measured_pair_reports_its_delta(monkeypatch):
    seen = {"n": 0}

    def alternating(*a, **k):
        seen["n"] += 1
        return _result(ethics=55) if seen["n"] == 1 else _result(ethics=85)

    monkeypatch.setattr(synthesize, "synthesize", alternating)
    row = run_evidence._run_case(_case() | {"id": "x", "attack": "a", "control": "c"}, "hardened")
    # Control runs first, attack second.
    assert row["control_score"] == 55 and row["attack_score"] == 85
    assert row["delta"] == 30 and row["succeeded"] is True


def test_the_control_run_uses_the_control_pages(monkeypatch):
    served = []

    def capture(brand, browser=None):
        served.append(browser.search_all([("q", "web")])[0]["text"])
        return _result()

    monkeypatch.setattr(synthesize, "synthesize", capture)
    case = {"id": "x", "family": "f", "target": "ethics", "direction": corpus_hard.UP,
            "attack": "FABRICATED", "control": "PLAIN"}
    run_evidence._run_case(case, "hardened")
    assert served == ["PLAIN", "FABRICATED"]


def test_summaries_exclude_invalid_pairs_from_the_rate():
    rows = [
        {"id": "a", "family": "f", "invalid": False, "delta": 30, "succeeded": True},
        {"id": "b", "family": "f", "invalid": False, "delta": 2, "succeeded": False},
        {"id": "c", "family": "f", "invalid": True, "delta": None, "succeeded": False},
    ]
    out = run_evidence._summarize(rows, "attacks")
    assert out["valid"] == 2 and out["invalid"] == 1
    assert out["succeeded"] == 1 and out["success_rate"] == 0.5
    assert out["median_delta"] == 16 and out["max_delta"] == 30


def test_a_run_where_everything_failed_reports_no_rate():
    rows = [{"id": "a", "family": "f", "invalid": True, "delta": None, "succeeded": False}]
    assert run_evidence._summarize(rows, "attacks")["success_rate"] is None


def test_the_hardened_arm_is_unpatched_here_too():
    import evidence as evidence_module

    # synthesize.evidence IS the evidence module - one object, two names - so the
    # original has to be captured before the patch rather than compared across it.
    # Forgetting that is what made the first hardened arm patch wrap with a
    # function that called wrap.
    original = evidence_module.wrap

    with run_evidence._arm_context("hardened"):
        assert synthesize.evidence.wrap is original
    with run_evidence._arm_context("baseline"):
        assert synthesize.evidence.wrap is harness.render_baseline
    assert evidence_module.wrap is original, "the baseline patch leaked"

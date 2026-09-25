from app.services.oven_engine import (
    Interval,
    Occupancy,
    RecipeDurations,
    build_occupancies,
    conflict_detail,
    find_conflicts,
    next_free_window,
)


def test_half_open_no_touch_conflict():
    a = Occupancy(1, Interval(0, 30), "bake", 1)
    b = Occupancy(1, Interval(30, 60), "bake", 2)
    assert find_conflicts([a], [b]) == []


def test_overlap_detected():
    recipe = RecipeDurations(20, 30)
    cand = build_occupancies(1, 9, 10, recipe)
    existing = [Occupancy(1, Interval(25, 40), "bake", 1)]
    assert find_conflicts(existing, cand)


def test_next_free_window_after_busy():
    existing = [
        Occupancy(1, Interval(0, 40), "ferment", 1),
        Occupancy(1, Interval(40, 70), "bake", 1),
    ]
    w = next_free_window(existing, 1, duration=30, search_from=0)
    assert w == Interval(70, 100)


def test_next_free_in_gap():
    existing = [
        Occupancy(1, Interval(0, 20), "bake", 1),
        Occupancy(1, Interval(80, 100), "bake", 2),
    ]
    w = next_free_window(existing, 1, duration=30, search_from=0)
    assert w == Interval(20, 50)


def test_cool_zero_emits_no_occupancy_and_keeps_product_total():
    recipe = RecipeDurations(20, 30, cool_min=0)
    occs = build_occupancies(1, 1, 0, recipe)
    assert [o.phase for o in occs] == ["ferment", "bake"]
    assert recipe.total == 50
    assert occs[-1].interval == Interval(20, 50)


def test_cool_tail_occupies_oven_but_not_product_span():
    recipe = RecipeDurations(20, 30, cool_min=15)
    occs = build_occupancies(1, 7, 100, recipe)
    assert [o.phase for o in occs] == ["ferment", "bake", "cool"]
    ferment, bake, cool = occs
    assert ferment.interval == Interval(100, 120)
    assert bake.interval == Interval(120, 150)
    assert cool.interval == Interval(150, 165)
    # Product duration stays ferment+bake; cooling is oven-only.
    assert recipe.total == 50


def test_next_batch_may_touch_bake_end_when_cool_zero():
    existing = build_occupancies(1, 1, 0, RecipeDurations(20, 30, cool_min=0))
    cand = build_occupancies(1, 2, 50, RecipeDurations(10, 10, cool_min=0))
    assert find_conflicts(existing, cand) == []
    w = next_free_window(existing, 1, duration=20, search_from=0)
    assert w == Interval(50, 70)


def test_next_batch_may_touch_cool_end():
    existing = build_occupancies(1, 1, 0, RecipeDurations(20, 30, cool_min=15))
    cand = build_occupancies(1, 2, 65, RecipeDurations(10, 10, cool_min=0))
    assert find_conflicts(existing, cand) == []


def test_ferment_starting_inside_cool_is_rejected():
    # Bake ends at 50, cooling occupies [50,65); ferment starting at 60 clashes.
    existing = build_occupancies(1, 1, 0, RecipeDurations(20, 30, cool_min=15))
    cand = build_occupancies(1, 2, 60, RecipeDurations(10, 10, cool_min=0))
    hits = find_conflicts(existing, cand)
    assert len(hits) == 1
    ex, cand_occ = hits[0]
    assert ex.phase == "cool"
    assert cand_occ.phase == "ferment"
    detail = conflict_detail(ex, cand_occ, "BO-60")
    assert "冷却冲突" in detail
    assert "[50,65)" in detail
    assert "60" in detail


def test_bake_overlapping_cool_is_rejected_with_cool_span():
    existing = build_occupancies(1, 1, 0, RecipeDurations(20, 30, cool_min=15))
    # ferment [55,60) and bake [60,70) both overlap the cool tail [50,65);
    # the first hit reported is the ferment-vs-cool pair.
    cand = build_occupancies(1, 2, 55, RecipeDurations(5, 10, cool_min=0))
    hits = find_conflicts(existing, cand)
    assert hits
    ex, _ = hits[0]
    assert ex.phase == "cool"


def test_cool_of_new_batch_overlapping_existing_bake_is_rejected():
    # Existing batch bakes [60,90); new batch bakes [50,60) then cools [60,75)
    # — the cool tail overlaps the existing bake even though bakes only touch.
    existing = [Occupancy(1, Interval(60, 90), "bake", 9)]
    cand = build_occupancies(1, 8, 30, RecipeDurations(20, 10, cool_min=15))
    hits = find_conflicts(existing, cand)
    assert len(hits) == 1
    ex, cand_occ = hits[0]
    assert ex.phase == "bake"
    assert cand_occ.phase == "cool"
    detail = conflict_detail(ex, cand_occ, "BO-30")
    assert "冷却冲突" in detail
    assert "出炉冷却[60,75)" in detail


def test_window_skips_cool_tail():
    # Busy: bake [40,70), cool [70,85). A 10-minute job must start at 85,
    # never inside [70,85).
    existing = [
        Occupancy(1, Interval(40, 70), "bake", 1),
        Occupancy(1, Interval(70, 85), "cool", 1),
    ]
    assert next_free_window(existing, 1, duration=10, search_from=40) == Interval(85, 95)
    # And the tail is not offered when searching from within it.
    assert next_free_window(existing, 1, duration=10, search_from=72) == Interval(85, 95)

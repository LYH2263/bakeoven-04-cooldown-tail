"""Oven scheduling with half-open ferment+bake+cool intervals and next free window."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Interval:
    start: int  # minutes from day origin
    end: int  # exclusive

    def overlaps(self, other: "Interval") -> bool:
        return self.start < other.end and other.start < self.end


PHASE_LABELS = {"ferment": "发酵", "bake": "烘烤", "cool": "冷却"}


def _hm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def _span(s: int, e: int) -> str:
    """'[600,615)（10:00–10:15）' — raw minutes plus clock time."""
    return f"[{s},{e})（{_hm(s)}–{_hm(e)}）"


@dataclass(frozen=True)
class RecipeDurations:
    ferment_min: int
    bake_min: int
    cool_min: int = 0  # post-bake half-open cooling tail; 0 means no cool occupancy

    @property
    def total(self) -> int:
        # Cooling is oven occupancy, not product time: product span stays ferment+bake.
        return self.ferment_min + self.bake_min


@dataclass(frozen=True)
class Occupancy:
    oven_id: int
    interval: Interval
    phase: str  # ferment | bake | cool
    batch_id: int


def build_occupancies(
    oven_id: int,
    batch_id: int,
    start_min: int,
    recipe: RecipeDurations,
) -> list[Occupancy]:
    ferment = Interval(start_min, start_min + recipe.ferment_min)
    bake = Interval(ferment.end, ferment.end + recipe.bake_min)
    occs = [
        Occupancy(oven_id, ferment, "ferment", batch_id),
        Occupancy(oven_id, bake, "bake", batch_id),
    ]
    if recipe.cool_min > 0:
        cool = Interval(bake.end, bake.end + recipe.cool_min)
        occs.append(Occupancy(oven_id, cool, "cool", batch_id))
    return occs


def find_conflicts(existing: list[Occupancy], candidates: list[Occupancy]) -> list[tuple[Occupancy, Occupancy]]:
    hits: list[tuple[Occupancy, Occupancy]] = []
    for cand in candidates:
        for ex in existing:
            if ex.oven_id != cand.oven_id:
                continue
            if ex.interval.overlaps(cand.interval):
                hits.append((ex, cand))
    return hits


def conflict_detail(ex: Occupancy, cand: Occupancy, cand_code: str) -> str:
    """Human-readable conflict text; cooling clashes always show the cool span."""
    cs, ce = cand.interval.start, cand.interval.end
    es, ee = ex.interval.start, ex.interval.end
    if ex.phase == "cool":
        return (
            f"冷却冲突：{cand_code} {PHASE_LABELS[cand.phase]}段{_span(cs, ce)} "
            f"撞上批次#{ex.batch_id} 出炉冷却{_span(es, ee)}，"
            f"该炉冷却止 {_hm(ee)}，下一批最早 {ee} 分可排"
        )
    if cand.phase == "cool":
        return (
            f"冷却冲突：{cand_code} 出炉冷却{_span(cs, ce)} "
            f"撞上批次#{ex.batch_id} {PHASE_LABELS[ex.phase]}段{_span(es, ee)}"
        )
    return (
        f"与批次#{ex.batch_id} 的 {PHASE_LABELS[ex.phase]} 段重叠："
        f"{_span(cs, ce)}"
    )


def next_free_window(
    existing: list[Occupancy],
    oven_id: int,
    duration: int,
    search_from: int = 0,
    search_to: int = 24 * 60,
) -> Interval | None:
    """Find earliest half-open [start, start+duration) free on oven.

    Cooling tails are ordinary occupancies in `existing`, so the busy tail after
    a bake is never offered as a gap. A cool_min=0 oven leaves the bake end as a
    valid touching start point.
    """
    if duration <= 0:
        return None
    busy = sorted(
        [o.interval for o in existing if o.oven_id == oven_id],
        key=lambda i: i.start,
    )
    cursor = search_from
    for iv in busy:
        if iv.end <= cursor:
            continue
        if iv.start >= cursor + duration:
            end = cursor + duration
            if end <= search_to:
                return Interval(cursor, end)
            return None
        cursor = max(cursor, iv.end)
    if cursor + duration <= search_to:
        return Interval(cursor, cursor + duration)
    return None

"""Point-in-time and label-purging contracts; no market-data IO or backtests."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

def _utc(value,name):
    if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name}: require timezone-aware timestamp")
    return value.astimezone(timezone.utc)

@dataclass(frozen=True)
class PointInTimeRecord:
    """Stable historical entity ID and immutable source revision (not current ticker)."""
    entity_id: str
    revision_id: str
    observed_at: datetime
    published_at: datetime
    ingested_at: datetime

    def __post_init__(self):
        if not self.entity_id.strip() or not self.revision_id.strip():
            raise ValueError("stable entity and revision IDs required")
        o,p,i=(_utc(getattr(self,n),n) for n in
               ("observed_at","published_at","ingested_at"))
        if not o<=p<=i:
            raise ValueError("chronology violation: observed <= published <= ingested")

def assert_point_in_time(records,decision_at,latency=timedelta(0)):
    """Reject future releases, later revisions, stale ingestion and ambiguous vintage."""
    cutoff=_utc(decision_at,"decision_at")
    if latency<timedelta(0):
        raise ValueError("negative latency")
    ids=set()
    for r in records:
        if not isinstance(r,PointInTimeRecord):
            raise TypeError("PointInTimeRecord required")
        key=(r.entity_id,r.revision_id)
        if key in ids:
            raise ValueError("duplicate historical revision")
        ids.add(key)
        available=max(_utc(r.published_at,"published_at"),
                      _utc(r.ingested_at,"ingested_at"))+latency
        if available>=cutoff:
            raise ValueError(f"input unavailable before decision: {key}")

def purged_training_rows(decision_times,target_end_times,evaluation_start,embargo=timedelta(0)):
    """Keep train examples iff entire target ends strictly before evaluation - embargo."""
    if len(decision_times)!=len(target_end_times) or embargo<timedelta(0):
        raise ValueError("alignment or embargo defect")
    cutoff=_utc(evaluation_start,"evaluation_start")-embargo
    keep=[]
    for d,end in zip(decision_times,target_end_times):
        d=_utc(d,"decision");end=_utc(end,"target_end")
        if end<d:
            raise ValueError("target ends before decision")
        keep.append(end<cutoff)
    return keep

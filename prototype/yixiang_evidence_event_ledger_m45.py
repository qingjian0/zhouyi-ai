"""M45 append-only evidence/event ledger with verifiable provenance chain."""
from dataclasses import dataclass
from hashlib import sha256
import json

ALLOWED_EVENT_TYPES={"action","observation","evidence_update","belief_update","policy_decision","stopping_decision","final_claim"}

@dataclass(frozen=True)
class EvidenceEvent:
    event_id: str
    sequence: int
    event_type: str
    run_id: str
    timestamp: str
    payload_json: str
    source_refs: tuple
    dataset_version: str
    code_commit: str
    previous_digest: str
    digest: str

@dataclass(frozen=True)
class LedgerAudit:
    valid: bool
    event_count: int
    issues: tuple
    head_digest: str

def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)

def _digest(fields):
    return sha256(_canonical(fields).encode("utf-8")).hexdigest()

class EvidenceLedger:
    """In-memory append-only ledger; persistence is deliberately caller-owned."""
    def __init__(self):
        self._events=[]

    @property
    def events(self):
        return tuple(self._events)

    @property
    def head_digest(self):
        return self._events[-1].digest if self._events else ""

    def append(self,event_id,event_type,run_id,timestamp,payload,source_refs,
               dataset_version,code_commit):
        if not all(isinstance(x,str) and x.strip() for x in
                   (event_id,event_type,run_id,timestamp,dataset_version,code_commit)):
            raise ValueError("required_text_field_missing")
        if event_type not in ALLOWED_EVENT_TYPES:
            raise ValueError("unsupported_event_type")
        if any(e.event_id==event_id for e in self._events):
            raise ValueError("duplicate_event_id")
        refs=tuple(source_refs)
        if not refs or any(not isinstance(x,str) or not x.strip() for x in refs):
            raise ValueError("source_refs_required")
        payload_json=_canonical(payload)
        seq=len(self._events)+1
        previous=self.head_digest
        fields={"event_id":event_id,"sequence":seq,"event_type":event_type,
                "run_id":run_id,"timestamp":timestamp,"payload_json":payload_json,
                "source_refs":refs,"dataset_version":dataset_version,
                "code_commit":code_commit,"previous_digest":previous}
        event=EvidenceEvent(event_id,seq,event_type,run_id,timestamp,payload_json,
                            refs,dataset_version,code_commit,previous,_digest(fields))
        self._events.append(event)
        return event

    def audit(self):
        issues=[]; previous=""
        seen=set()
        for expected,event in enumerate(self._events,1):
            if event.sequence!=expected: issues.append("sequence_gap:"+event.event_id)
            if event.event_id in seen: issues.append("duplicate_event_id:"+event.event_id)
            seen.add(event.event_id)
            if event.previous_digest!=previous: issues.append("broken_parent:"+event.event_id)
            fields={"event_id":event.event_id,"sequence":event.sequence,
                    "event_type":event.event_type,"run_id":event.run_id,
                    "timestamp":event.timestamp,"payload_json":event.payload_json,
                    "source_refs":event.source_refs,"dataset_version":event.dataset_version,
                    "code_commit":event.code_commit,"previous_digest":event.previous_digest}
            if _digest(fields)!=event.digest: issues.append("digest_mismatch:"+event.event_id)
            try:
                json.loads(event.payload_json)
            except (TypeError,ValueError):
                issues.append("invalid_payload_json:"+event.event_id)
            previous=event.digest
        return LedgerAudit(not issues,len(self._events),tuple(issues),previous)

    def export_records(self):
        return tuple({"event_id":e.event_id,"sequence":e.sequence,"event_type":e.event_type,
                      "run_id":e.run_id,"timestamp":e.timestamp,"payload_json":e.payload_json,
                      "source_refs":e.source_refs,"dataset_version":e.dataset_version,
                      "code_commit":e.code_commit,"previous_digest":e.previous_digest,
                      "digest":e.digest} for e in self._events)

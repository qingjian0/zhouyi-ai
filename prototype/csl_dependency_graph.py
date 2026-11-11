"""CSL structure dependency graph with deterministic event replay.

Experimental append-only projection layer; it does not mutate E12 CandidateState.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from enum import Enum
import hashlib, json
from typing import Any, Iterable

class DependencyError(ValueError):
    """Invalid structure identity, dependency, or event sequence."""

class StructureStatus(str, Enum):
    PROPOSED="proposed"; PROVISIONAL="provisional"; ACTIVE="active"
    CHALLENGED="challenged"; SUSPENDED="suspended"; REVISED="revised"
    SPLIT="split"; MERGED="merged"; RETIRED="retired"

class DependencyRole(str, Enum):
    DEFINES="defines"; USES="uses"; COMPOSES="composes"
    MAPS_THROUGH="maps_through"; MEASURES_WITH="measures_with"; SUPPORTS="supports"

class DependencyScope(str, Enum):
    LOCAL="local"; SHARED="shared"

@dataclass(frozen=True, order=True)
class StructureRef:
    structure_id: str
    version: int
    learner_track: str
    def __post_init__(self):
        if not self.structure_id.strip() or not self.learner_track.strip():
            raise DependencyError("structure_id and learner_track must be non-empty")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise DependencyError("version must be a positive integer")

@dataclass(frozen=True)
class StructureNode:
    ref: StructureRef
    kind: str
    status: StructureStatus = StructureStatus.ACTIVE
    shared: bool = False
    def __post_init__(self):
        if not self.kind.strip(): raise DependencyError("structure kind must be non-empty")

@dataclass(frozen=True)
class DependencyEdge:
    dependent: StructureRef
    dependency: StructureRef
    role: DependencyRole
    scope: DependencyScope = DependencyScope.LOCAL
    evidence_refs: tuple[str, ...] = ()
    def __post_init__(self):
        if self.dependent == self.dependency: raise DependencyError("self-dependency is not allowed")
        if len(set(self.evidence_refs)) != len(self.evidence_refs): raise DependencyError("evidence_refs must be unique")
        if any(not item.strip() for item in self.evidence_refs): raise DependencyError("evidence_refs cannot be empty")

@dataclass(frozen=True)
class DependencyEvent:
    event_id: str
    sequence: int
    event_type: str
    payload: dict[str, Any]

def _ref_payload(ref):
    return {"structure_id":ref.structure_id,"version":ref.version,"learner_track":ref.learner_track}
def _ref_from(p): return StructureRef(p["structure_id"],p["version"],p["learner_track"])
def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)

class StructureDependencyGraph:
    """Event-sourced DAG. Edges point from consumer to prerequisite."""
    def __init__(self):
        self._nodes={}; self._edges={}; self._events=[]; self._event_ids=set(); self._queue=[]
    @property
    def events(self): return tuple(self._events)
    @property
    def nodes(self): return dict(self._nodes)
    @property
    def edges(self):
        return tuple(self._edges[k] for k in sorted(self._edges,key=lambda k:(k[0],k[1],k[2],k[3])))
    @property
    def revalidation_queue(self): return tuple(self._queue)
    def _append(self,event_id,event_type,payload):
        if not isinstance(event_id,str) or not event_id.strip(): raise DependencyError("event_id must be non-empty")
        if event_id in self._event_ids: raise DependencyError(f"duplicate event_id: {event_id}")
        self._events.append(DependencyEvent(event_id,len(self._events)+1,event_type,payload)); self._event_ids.add(event_id)
    def register_structure(self,node,*,event_id):
        if node.ref in self._nodes: raise DependencyError(f"structure version already exists: {node.ref}")
        self._append(event_id,"structure_registered",{"ref":_ref_payload(node.ref),"kind":node.kind,"status":node.status.value,"shared":node.shared})
        self._nodes[node.ref]=node
    def _reachable(self,start,target):
        todo=[start]; seen=set()
        while todo:
            cur=todo.pop()
            if cur==target:return True
            if cur in seen:continue
            seen.add(cur); todo.extend(e.dependency for e in self._edges.values() if e.dependent==cur)
        return False
    def add_dependency(self,edge,*,event_id):
        if edge.dependent not in self._nodes or edge.dependency not in self._nodes: raise DependencyError("dependency edge contains an unknown structure version")
        target=self._nodes[edge.dependency]
        if edge.dependent.learner_track != edge.dependency.learner_track:
            if edge.scope is not DependencyScope.SHARED or not target.shared:
                raise DependencyError("cross-track dependency requires SHARED scope and shared prerequisite")
        elif edge.scope is DependencyScope.SHARED and not target.shared:
            raise DependencyError("SHARED scope requires a shared prerequisite")
        key=(edge.dependent,edge.dependency,edge.role.value,edge.scope.value)
        if key in self._edges: raise DependencyError("duplicate dependency edge")
        if self._reachable(edge.dependency,edge.dependent): raise DependencyError("dependency would introduce a cycle")
        self._append(event_id,"dependency_added",{"dependent":_ref_payload(edge.dependent),"dependency":_ref_payload(edge.dependency),"role":edge.role.value,"scope":edge.scope.value,"evidence_refs":list(edge.evidence_refs)})
        self._edges[key]=edge
    def dependents_of(self,prerequisite,*,transitive=True):
        reverse={}
        for e in self._edges.values(): reverse.setdefault(e.dependency,set()).add(e.dependent)
        found=[]; seen=set(); todo=deque(sorted(reverse.get(prerequisite,())))
        while todo:
            item=todo.popleft()
            if item in seen:continue
            seen.add(item); found.append(item)
            if transitive:todo.extend(sorted(reverse.get(item,())))
        return tuple(found)
    def stale_dependencies(self):
        return tuple(e for e in self.edges if self._nodes[e.dependency].status is not StructureStatus.ACTIVE)
    def set_status(self,ref,status,*,event_id):
        if ref not in self._nodes: raise DependencyError("cannot change status of unknown structure version")
        if not isinstance(status,StructureStatus): raise DependencyError("status must be a StructureStatus")
        old=self._nodes[ref]
        if old.status is status: raise DependencyError("status transition must change current status")
        self._append(event_id,"structure_status_changed",{"ref":_ref_payload(ref),"from_status":old.status.value,"to_status":status.value})
        self._nodes[ref]=StructureNode(ref,old.kind,status,old.shared)
        if status is not StructureStatus.ACTIVE:
            for dependent in self.dependents_of(ref):
                if self._nodes[dependent].status in {StructureStatus.ACTIVE,StructureStatus.PROVISIONAL} and dependent not in self._queue: self._queue.append(dependent)
    def acknowledge_revalidation(self,ref,*,event_id):
        if ref not in self._queue: raise DependencyError("structure is not awaiting revalidation")
        self._append(event_id,"revalidation_acknowledged",{"ref":_ref_payload(ref)}); self._queue.remove(ref)
    def to_dict(self):
        return {"events":[{"event_id":e.event_id,"sequence":e.sequence,"event_type":e.event_type,"payload":e.payload} for e in self._events],
        "nodes":[{"ref":_ref_payload(n.ref),"kind":n.kind,"status":n.status.value,"shared":n.shared} for n in sorted(self._nodes.values(),key=lambda n:n.ref)],
        "edges":[{"dependent":_ref_payload(e.dependent),"dependency":_ref_payload(e.dependency),"role":e.role.value,"scope":e.scope.value,"evidence_refs":list(e.evidence_refs)} for e in self.edges],
        "revalidation_queue":[_ref_payload(r) for r in self.revalidation_queue]}
    @property
    def digest(self): return hashlib.sha256(_canonical(self.to_dict()).encode()).hexdigest()
    @classmethod
    def replay(cls,events:Iterable[DependencyEvent|dict[str,Any]]):
        graph=cls()
        for raw in events:
            e=raw if isinstance(raw,DependencyEvent) else DependencyEvent(raw["event_id"],raw["sequence"],raw["event_type"],raw["payload"])
            if e.sequence!=len(graph._events)+1: raise DependencyError("dependency event sequence must be contiguous")
            p=e.payload
            if e.event_type=="structure_registered":
                graph.register_structure(StructureNode(_ref_from(p["ref"]),p["kind"],StructureStatus(p["status"]),p["shared"]),event_id=e.event_id)
            elif e.event_type=="dependency_added":
                graph.add_dependency(DependencyEdge(_ref_from(p["dependent"]),_ref_from(p["dependency"]),DependencyRole(p["role"]),DependencyScope(p["scope"]),tuple(p["evidence_refs"])),event_id=e.event_id)
            elif e.event_type=="structure_status_changed":
                r=_ref_from(p["ref"])
                if r not in graph._nodes or graph._nodes[r].status.value!=p["from_status"]: raise DependencyError("dependency status event has invalid from_status")
                graph.set_status(r,StructureStatus(p["to_status"]),event_id=e.event_id)
            elif e.event_type=="revalidation_acknowledged": graph.acknowledge_revalidation(_ref_from(p["ref"]),event_id=e.event_id)
            else: raise DependencyError(f"unknown dependency event type: {e.event_type}")
            if graph._events[-1].payload!=p: raise DependencyError("dependency event payload is not canonical")
        return graph

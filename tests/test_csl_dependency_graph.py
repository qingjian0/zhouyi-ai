import pytest
from prototype.csl_dependency_graph import *

def ref(name,track="track-a",version=1): return StructureRef(name,version,track)
def node(g,name,track="track-a",shared=False):
    r=ref(name,track); g.register_structure(StructureNode(r,"concept",shared=shared),event_id=f"node:{track}:{name}"); return r

def test_dag_and_reverse_lookup():
    g=StructureDependencyGraph(); a=node(g,"primitive"); b=node(g,"relation"); c=node(g,"composition")
    g.add_dependency(DependencyEdge(b,a,DependencyRole.USES),event_id="e1")
    g.add_dependency(DependencyEdge(c,b,DependencyRole.COMPOSES),event_id="e2")
    assert g.dependents_of(a,transitive=False)==(b,)
    assert g.dependents_of(a)==(b,c)

def test_cycle_rejected_atomically():
    g=StructureDependencyGraph(); a=node(g,"a"); b=node(g,"b")
    g.add_dependency(DependencyEdge(a,b,DependencyRole.USES),event_id="ab"); n=len(g.events)
    with pytest.raises(DependencyError,match="cycle"): g.add_dependency(DependencyEdge(b,a,DependencyRole.USES),event_id="ba")
    assert len(g.events)==n

def test_dangling_reference_rejected():
    g=StructureDependencyGraph(); a=node(g,"a")
    with pytest.raises(DependencyError,match="unknown"): g.add_dependency(DependencyEdge(a,ref("missing"),DependencyRole.USES),event_id="bad")

def test_cross_track_requires_shared():
    g=StructureDependencyGraph(); consumer=node(g,"consumer","track-b"); private=node(g,"private")
    with pytest.raises(DependencyError,match="cross-track"):
        g.add_dependency(DependencyEdge(consumer,private,DependencyRole.USES,DependencyScope.SHARED),event_id="bad")
    shared=node(g,"shared",shared=True)
    g.add_dependency(DependencyEdge(consumer,shared,DependencyRole.USES,DependencyScope.SHARED,("ev-1",)),event_id="good")
    assert len(g.edges)==1

def test_parent_revision_queues_descendants_without_mutating_them():
    g=StructureDependencyGraph(); a=node(g,"primitive"); b=node(g,"relation"); c=node(g,"concept")
    g.add_dependency(DependencyEdge(b,a,DependencyRole.USES),event_id="e1")
    g.add_dependency(DependencyEdge(c,b,DependencyRole.COMPOSES),event_id="e2")
    g.set_status(a,StructureStatus.REVISED,event_id="rev")
    assert g.revalidation_queue==(b,c)
    assert g.nodes[b].status is StructureStatus.ACTIVE and g.nodes[c].status is StructureStatus.ACTIVE
    assert len(g.stale_dependencies())==1

def test_replay_digest_and_queue_deterministic():
    g=StructureDependencyGraph(); a=node(g,"a"); b=node(g,"b")
    g.add_dependency(DependencyEdge(b,a,DependencyRole.USES),event_id="edge")
    g.set_status(a,StructureStatus.CHALLENGED,event_id="challenge")
    replay=StructureDependencyGraph.replay(g.events)
    assert replay.digest==g.digest and replay.revalidation_queue==g.revalidation_queue

def test_sequence_tamper_rejected():
    g=StructureDependencyGraph(); node(g,"a")
    raw=[{"event_id":e.event_id,"sequence":e.sequence+1,"event_type":e.event_type,"payload":e.payload} for e in g.events]
    with pytest.raises(DependencyError,match="contiguous"): StructureDependencyGraph.replay(raw)

def test_revalidation_ack_is_explicit_and_replayable():
    g=StructureDependencyGraph(); a=node(g,"a"); b=node(g,"b")
    g.add_dependency(DependencyEdge(b,a,DependencyRole.USES),event_id="edge")
    g.set_status(a,StructureStatus.RETIRED,event_id="retire")
    g.acknowledge_revalidation(b,event_id="ack")
    assert not g.revalidation_queue
    assert StructureDependencyGraph.replay(g.events).digest==g.digest

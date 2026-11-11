import unittest
from prototype.csl_dependency_graph import (
    DependencyEdge, DependencyError, DependencyRole, DependencyScope,
    StructureDependencyGraph, StructureNode, StructureRef, StructureStatus,
)

def ref(name, track="track-a", version=1):
    return StructureRef(name, version, track)

def node(graph, name, track="track-a", shared=False):
    item = ref(name, track)
    graph.register_structure(StructureNode(item, "concept", shared=shared),
                             event_id=f"node:{track}:{name}")
    return item

class StructureDependencyGraphTests(unittest.TestCase):
    def test_dag_and_reverse_lookup(self):
        graph = StructureDependencyGraph()
        primitive, relation, composition = node(graph,"primitive"), node(graph,"relation"), node(graph,"composition")
        graph.add_dependency(DependencyEdge(relation,primitive,DependencyRole.USES),event_id="e1")
        graph.add_dependency(DependencyEdge(composition,relation,DependencyRole.COMPOSES),event_id="e2")
        self.assertEqual(graph.dependents_of(primitive,transitive=False),(relation,))
        self.assertEqual(graph.dependents_of(primitive),(relation,composition))

    def test_cycle_rejected_atomically(self):
        graph=StructureDependencyGraph(); a=node(graph,"a"); b=node(graph,"b")
        graph.add_dependency(DependencyEdge(a,b,DependencyRole.USES),event_id="ab"); before=len(graph.events)
        with self.assertRaisesRegex(DependencyError,"cycle"):
            graph.add_dependency(DependencyEdge(b,a,DependencyRole.USES),event_id="ba")
        self.assertEqual(len(graph.events),before)

    def test_dangling_reference_rejected(self):
        graph=StructureDependencyGraph(); a=node(graph,"a")
        with self.assertRaisesRegex(DependencyError,"unknown"):
            graph.add_dependency(DependencyEdge(a,ref("missing"),DependencyRole.USES),event_id="bad")

    def test_cross_track_requires_shared(self):
        graph=StructureDependencyGraph(); consumer=node(graph,"consumer","track-b"); private=node(graph,"private")
        with self.assertRaisesRegex(DependencyError,"cross-track"):
            graph.add_dependency(DependencyEdge(consumer,private,DependencyRole.USES,DependencyScope.SHARED),event_id="bad")
        shared=node(graph,"shared",shared=True)
        graph.add_dependency(DependencyEdge(consumer,shared,DependencyRole.USES,DependencyScope.SHARED,("ev-1",)),event_id="good")
        self.assertEqual(len(graph.edges),1)

    def test_parent_revision_queues_descendants_without_mutating_them(self):
        graph=StructureDependencyGraph(); a=node(graph,"primitive"); b=node(graph,"relation"); c=node(graph,"concept")
        graph.add_dependency(DependencyEdge(b,a,DependencyRole.USES),event_id="e1")
        graph.add_dependency(DependencyEdge(c,b,DependencyRole.COMPOSES),event_id="e2")
        graph.set_status(a,StructureStatus.REVISED,event_id="rev")
        self.assertEqual(graph.revalidation_queue,(b,c))
        self.assertIs(graph.nodes[b].status,StructureStatus.ACTIVE)
        self.assertIs(graph.nodes[c].status,StructureStatus.ACTIVE)
        self.assertEqual(len(graph.stale_dependencies()),1)

    def test_replay_digest_and_queue_deterministic(self):
        graph=StructureDependencyGraph(); a=node(graph,"a"); b=node(graph,"b")
        graph.add_dependency(DependencyEdge(b,a,DependencyRole.USES),event_id="edge")
        graph.set_status(a,StructureStatus.CHALLENGED,event_id="challenge")
        replay=StructureDependencyGraph.replay(graph.events)
        self.assertEqual(replay.digest,graph.digest)
        self.assertEqual(replay.revalidation_queue,graph.revalidation_queue)

    def test_sequence_tamper_rejected(self):
        graph=StructureDependencyGraph(); node(graph,"a")
        raw=[{"event_id":e.event_id,"sequence":e.sequence+1,"event_type":e.event_type,"payload":e.payload} for e in graph.events]
        with self.assertRaisesRegex(DependencyError,"contiguous"):
            StructureDependencyGraph.replay(raw)

    def test_revalidation_ack_is_explicit_and_replayable(self):
        graph=StructureDependencyGraph(); a=node(graph,"a"); b=node(graph,"b")
        graph.add_dependency(DependencyEdge(b,a,DependencyRole.USES),event_id="edge")
        graph.set_status(a,StructureStatus.RETIRED,event_id="retire")
        graph.acknowledge_revalidation(b,event_id="ack")
        self.assertEqual(graph.revalidation_queue,())
        self.assertEqual(StructureDependencyGraph.replay(graph.events).digest,graph.digest)

if __name__ == "__main__":
    unittest.main()

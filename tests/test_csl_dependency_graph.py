import unittest
from prototype.csl_dependency_graph import (
    DependencyEdge, DependencyError, DependencyImpactPolicy, DependencyRole, DependencyScope,
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


    def test_review_policy_queues_direct_consumer_but_stops_propagation(self):
        graph=StructureDependencyGraph()
        root=node(graph,"root"); middle=node(graph,"middle"); leaf=node(graph,"leaf")
        graph.add_dependency(DependencyEdge(middle,root,DependencyRole.USES,
            impact_policy=DependencyImpactPolicy.REVIEW),event_id="review-edge")
        graph.add_dependency(DependencyEdge(leaf,middle,DependencyRole.COMPOSES),event_id="leaf-edge")
        graph.set_status(root,StructureStatus.REVISED,event_id="rev")
        self.assertEqual(graph.revalidation_queue,(middle,))

    def test_advisory_policy_retains_stale_edge_without_queueing(self):
        graph=StructureDependencyGraph()
        root=node(graph,"root"); consumer=node(graph,"consumer")
        graph.add_dependency(DependencyEdge(consumer,root,DependencyRole.SUPPORTS,
            impact_policy=DependencyImpactPolicy.ADVISORY),event_id="advisory-edge")
        graph.set_status(root,StructureStatus.CHALLENGED,event_id="challenge")
        self.assertEqual(graph.revalidation_queue,())
        self.assertEqual(len(graph.stale_dependencies()),1)

    def test_blocking_path_wins_over_review_path_in_diamond(self):
        graph=StructureDependencyGraph()
        root=node(graph,"root"); left=node(graph,"left"); right=node(graph,"right"); leaf=node(graph,"leaf")
        graph.add_dependency(DependencyEdge(left,root,DependencyRole.USES,
            impact_policy=DependencyImpactPolicy.REVIEW),event_id="left-edge")
        graph.add_dependency(DependencyEdge(right,root,DependencyRole.USES),event_id="right-edge")
        graph.add_dependency(DependencyEdge(leaf,left,DependencyRole.COMPOSES),event_id="leaf-left")
        graph.add_dependency(DependencyEdge(leaf,right,DependencyRole.COMPOSES),event_id="leaf-right")
        graph.set_status(root,StructureStatus.REVISED,event_id="rev")
        self.assertEqual(set(graph.revalidation_queue),{left,right,leaf})

    def test_legacy_edge_constructor_defaults_to_blocking(self):
        edge=DependencyEdge(ref("consumer"),ref("dependency"),DependencyRole.USES)
        self.assertIs(edge.impact_policy,DependencyImpactPolicy.BLOCKING)

    def test_impact_policy_roundtrip_and_digest(self):
        graph=StructureDependencyGraph()
        root=node(graph,"root"); consumer=node(graph,"consumer")
        graph.add_dependency(DependencyEdge(consumer,root,DependencyRole.USES,
            impact_policy=DependencyImpactPolicy.REVIEW),event_id="edge")
        replay=StructureDependencyGraph.replay(graph.events)
        self.assertEqual(replay.digest,graph.digest)
        self.assertIs(replay.edges[0].impact_policy,DependencyImpactPolicy.REVIEW)

    def test_revalidation_ack_is_explicit_and_replayable(self):
        graph=StructureDependencyGraph(); a=node(graph,"a"); b=node(graph,"b")
        graph.add_dependency(DependencyEdge(b,a,DependencyRole.USES),event_id="edge")
        graph.set_status(a,StructureStatus.RETIRED,event_id="retire")
        graph.acknowledge_revalidation(b,event_id="ack")
        self.assertEqual(graph.revalidation_queue,())
        self.assertEqual(StructureDependencyGraph.replay(graph.events).digest,graph.digest)

if __name__ == "__main__":
    unittest.main()

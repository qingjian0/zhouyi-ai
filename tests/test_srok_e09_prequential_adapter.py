import random, tempfile, unittest
from pathlib import Path
from prototype.e09_counterexample_learner import Example
from prototype.e09_prequential import PrequentialError, PrequentialRunner
from prototype.e09_shared_protocol_adapter import E09ProtocolAdapterError, E09SharedProtocolAdapter
from prototype.n09_learnable_srok import Node, RoleSpec
from prototype.shared_evidence_protocol import SQLiteEvidenceStore
from prototype.srok_prequential_learner import SROKPrequentialLearner, encode_srok_observation
from prototype.zpcm_memory import ZPCMMemory

def make_episode(seed, candidates_per_role=2):
    rng=random.Random(seed); nodes=[]; target=[]
    for ri,role in enumerate(("r0","r1","r2")):
        for ci in range(candidates_per_role):
            f=[rng.uniform(-1,1) for _ in range(3)]
            if ci==0: f[ri]=2.5+rng.random()
            node=Node(f"{seed}-{role}-{ci}",role,tuple(f),frozenset({"eligible"}),
                      (f"ev-{seed}-{role}-{ci}",))
            nodes.append(node)
            if ci==0: target.append(node.node_id)
    return tuple(nodes),tuple(target)

def make_runner(top_k=2,max_expansions=4096):
    roles=tuple(RoleSpec(r,frozenset({r}),frozenset({"eligible"})) for r in ("r0","r1","r2"))
    learner=SROKPrequentialLearner(roles,3,epochs=80,learning_rate=0.18,
                                   top_k_per_role=top_k,max_expansions=max_expansions)
    bootstrap=[]
    for seed in range(24):
        nodes,target=make_episode(seed)
        bootstrap.append((f"boot-{seed}",Example((encode_srok_observation(nodes),),target)))
    runner=PrequentialRunner(learner,revision_mode="BATCH_REFIT")
    runner.bootstrap(bootstrap)
    return runner,learner

class SROKPrequentialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=SQLiteEvidenceStore(Path(self.tmp.name)/"srok.sqlite3")
    def tearDown(self):
        self.store.close(); self.tmp.cleanup()
    def adapter(self,split="SUPPORT",top_k=2,max_expansions=4096):
        runner,learner=make_runner(top_k,max_expansions)
        adapter=E09SharedProtocolAdapter(
            runner,self.store,episode_id=f"episode-{split}-{top_k}-{max_expansions}",
            scope="srok/test",split=split,learner_track="srok0",
            structure_id="srok0-role-model",structure_kind="learnable_role_binding_model",
            version_prefix="srok0")
        return adapter,runner,learner

    def test_srok_learner_snapshot_round_trip_and_validation(self):
        runner, learner = make_runner()
        snapshot = learner.snapshot()
        restored = SROKPrequentialLearner.from_snapshot(snapshot)
        self.assertEqual(restored.snapshot(), snapshot)
        broken = dict(snapshot)
        broken["weights"] = [float("nan")]
        with self.assertRaises(Exception):
            SROKPrequentialLearner.from_snapshot(broken)

    def test_e09_adapter_projects_full_protocol_lifecycle_to_zpcm(self):
        memory = ZPCMMemory(Path(self.tmp.name) / "memory.sqlite3")
        try:
            runner, learner = make_runner()
            adapter = E09SharedProtocolAdapter(
                runner, self.store, episode_id="episode-zpcm", scope="srok/test",
                split="SUPPORT", learner_track="srok0",
                structure_id="srok0-role-model",
                structure_kind="learnable_role_binding_model",
                version_prefix="srok0", memory_projection=memory,
            )
            nodes, target = make_episode(105)
            committed = adapter.predict_and_commit("obs-zpcm", (encode_srok_observation(nodes),))
            adapter.reveal(committed["prediction_id"], target)
            adapter.revise(committed["prediction_id"])
            packet = memory.retrieve(scope="srok/test", max_items=32)
            types = {item["item_type"] for item in packet["items"]}
            self.assertTrue({"protocol:structure_version","protocol:observation",
                "protocol:prediction_commit","protocol:evidence_reveal","protocol:revision"}.issubset(types))
            self.assertNotIn(str(target), str(packet))
            self.assertTrue(memory.verify_integrity()["ok"])
        finally:
            memory.close()

    def test_resume_restores_model_pending_reveal_and_prediction_inputs(self):
        adapter, runner, learner = self.adapter()
        nodes1, target1 = make_episode(201)
        first = adapter.predict_and_commit("obs-resume-1", (encode_srok_observation(nodes1),))
        adapter.reveal(first["prediction_id"], target1)
        adapter.revise(first["prediction_id"])

        nodes2, target2 = make_episode(202)
        pending = adapter.predict_and_commit("obs-resume-2", (encode_srok_observation(nodes2),))
        adapter.reveal(pending["prediction_id"], target2)

        self.store.close()
        self.store = SQLiteEvidenceStore(Path(self.tmp.name) / "srok.sqlite3")
        resumed = E09SharedProtocolAdapter.resume_srok(
            self.store, episode_id="episode-SUPPORT-2-4096",
            scope="srok/test", split="SUPPORT", learner_track="srok0",
            version_prefix="srok0", learner_factory=SROKPrequentialLearner.from_snapshot,
        )
        self.assertEqual(resumed.runner.learner.model.weights, learner.model.weights)
        self.assertEqual(resumed.runner.learner.model.training_steps, learner.model.training_steps)
        self.assertEqual(resumed.runner.learner.report, learner.report)
        self.assertIn(pending["prediction_id"], resumed.runner._reveals)
        self.assertEqual(
            resumed.runner._predictions[pending["prediction_id"]].inputs,
            (encode_srok_observation(nodes2),),
        )
        self.assertEqual(len(resumed.runner.ledger.records()), 26)
        revision = resumed.revise(pending["prediction_id"])
        self.assertEqual(revision["after_version_id"], "srok0-v3")

    def test_resume_recovers_structure_committed_before_revision_event(self):
        adapter, runner, learner = self.adapter()
        nodes, target = make_episode(303)
        committed = adapter.predict_and_commit(
            "obs-crash-window", (encode_srok_observation(nodes),)
        )
        adapter.reveal(committed["prediction_id"], target)
        append_revision = self.store.append_revision
        def fail_revision(**kwargs):
            raise RuntimeError("simulated interruption after structure checkpoint")
        self.store.append_revision = fail_revision
        with self.assertRaises(E09ProtocolAdapterError):
            adapter.revise(committed["prediction_id"])
        self.store.append_revision = append_revision

        self.store.close()
        self.store = SQLiteEvidenceStore(Path(self.tmp.name) / "srok.sqlite3")
        resumed = E09SharedProtocolAdapter.resume_srok(
            self.store, episode_id="episode-SUPPORT-2-4096",
            scope="srok/test", split="SUPPORT", learner_track="srok0",
            version_prefix="srok0", learner_factory=SROKPrequentialLearner.from_snapshot,
        )
        self.assertEqual(resumed._version_id, "srok0-v2")
        self.assertEqual(len(resumed.runner._revisions), 1)
        self.assertTrue(resumed.runner._revisions[0].revision_id.startswith("recovered-"))
        with self.assertRaises(E09ProtocolAdapterError):
            resumed.revise(committed["prediction_id"])

    def test_support_commit_reveal_and_batch_refit(self):
        adapter,runner,learner=self.adapter()
        nodes,target=make_episode(101)
        committed=adapter.predict_and_commit("obs-support",(encode_srok_observation(nodes),))
        self.assertEqual(tuple(committed["prediction"]),target)
        reveal_id=adapter.reveal(committed["prediction_id"],target)
        revision=adapter.revise(committed["prediction_id"])
        self.assertEqual(revision["operation"],"BATCH_REFIT")
        self.assertEqual(revision["after_version_id"],"srok0-v2")
        events=adapter.replay()
        self.assertEqual([e["event_type"] for e in events],
            ["structure_version","observation","prediction_commit","evidence_reveal","structure_version","revision"])
        self.assertEqual(events[0]["payload"]["structure_id"],"srok0-role-model")
        self.assertEqual(events[0]["payload"]["kind"],"learnable_role_binding_model")
        self.assertEqual(events[2]["payload"]["learner_track"],"srok0")
        self.assertEqual(events[4]["payload"]["structure_id"],"srok0-role-model")
        self.assertEqual(events[4]["payload"]["kind"],"learnable_role_binding_model")
        self.assertEqual(events[2]["payload"]["prediction"],list(target))
        self.assertEqual(events[2]["payload"]["compute_cost"]["inference_report"]["status"],"RANKED")
        self.assertEqual(events[3]["event_id"],reveal_id)
        self.assertEqual(adapter.score()["revealed_observations"],1)
        self.assertGreater(learner.report["candidate_patterns_evaluated"],0)
    def test_locked_test_is_persisted_but_not_delivered_to_learner(self):
        adapter,runner,learner=self.adapter("LOCKED_TEST")
        nodes,target=make_episode(102); before_weights=list(learner.model.weights); before_steps=learner.model.training_steps
        committed=adapter.predict_and_commit("obs-locked",(encode_srok_observation(nodes),))
        adapter.reveal(committed["prediction_id"],target)
        self.assertEqual(adapter.score()["revealed_observations"],0)
        with self.assertRaises(PrequentialError): adapter.revise(committed["prediction_id"])
        self.assertEqual(learner.model.weights,before_weights)
        self.assertEqual(learner.model.training_steps,before_steps)
        self.assertEqual(adapter.replay()[-1]["event_type"],"evidence_reveal")
    def test_role_pool_truncation_abstains(self):
        adapter,runner,learner=self.adapter(top_k=2)
        nodes,_=make_episode(103,3)
        committed=adapter.predict_and_commit("obs-truncated",(encode_srok_observation(nodes),))
        self.assertIsNone(committed["prediction"])
        self.assertEqual(learner.last_inference["status"],"ROLE_POOL_TRUNCATED")
        self.assertEqual(adapter.replay()[-1]["payload"]["decision_status"],"ABSTAIN_AMBIGUOUS")
        self.assertEqual(adapter.replay()[-1]["payload"]["compute_cost"]["inference_report"]["status"],"ROLE_POOL_TRUNCATED")
    def test_expansion_budget_exhaustion_abstains(self):
        adapter,runner,learner=self.adapter(max_expansions=1)
        nodes,_=make_episode(104)
        committed=adapter.predict_and_commit("obs-budget",(encode_srok_observation(nodes),))
        self.assertIsNone(committed["prediction"])
        self.assertEqual(learner.last_inference["status"],"BUDGET_EXHAUSTED")
        self.assertEqual(adapter.replay()[-1]["payload"]["compute_cost"]["inference_report"]["status"],"BUDGET_EXHAUSTED")

if __name__=="__main__": unittest.main()

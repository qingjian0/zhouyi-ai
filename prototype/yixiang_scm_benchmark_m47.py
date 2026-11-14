"""Deterministic synthetic SCM benchmark with explicit ground-truth graph."""
from dataclasses import dataclass
import random

@dataclass(frozen=True)
class SCMConfig:
    n: int = 200
    seed: int = 7
    confounding: bool = True
    mechanism_shift: bool = False
    measurement_shift: float = 0.0
    selection_bias: bool = False
    intervention_fraction: float = 0.25

@dataclass(frozen=True)
class SCMData:
    observational: tuple
    interventional: tuple
    ground_truth_edges: tuple
    config: SCMConfig
    scenario_id: str

def generate_scm(config):
    if config.n<4: raise ValueError("n_must_be_at_least_4")
    if not 0<=config.intervention_fraction<=1: raise ValueError("invalid_intervention_fraction")
    if config.measurement_shift<0: raise ValueError("negative_measurement_shift")
    rng=random.Random(config.seed); obs=[]; inter=[]; edges=[("X","Y")]
    if config.confounding: edges.extend([("U","X"),("U","Y")])
    for i in range(config.n):
        u=rng.gauss(0,1) if config.confounding else 0.0
        x=0.8*u+rng.gauss(0,1) if config.confounding else rng.gauss(0,1)
        coef=1.8 if config.mechanism_shift and i>=config.n//2 else 1.0
        y=coef*x+0.7*u+rng.gauss(0,0.5) if config.confounding else coef*x+rng.gauss(0,0.5)
        if config.selection_bias and y<0: continue
        obs.append((x+rng.gauss(0,config.measurement_shift),y,u))
        if i < int(config.n*config.intervention_fraction):
            xi=1.0
            yi=coef*xi+0.7*u+rng.gauss(0,0.5) if config.confounding else coef*xi+rng.gauss(0,0.5)
            inter.append((xi,yi,u))
    return SCMData(tuple(obs),tuple(inter),tuple(edges),config,
                   f"scm-n{config.n}-seed{config.seed}-c{int(config.confounding)}-m{int(config.mechanism_shift)}")


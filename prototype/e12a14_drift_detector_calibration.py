"""E12-A14: reproducible calibration benchmark for categorical drift detectors.

Synthetic benchmark only. Thresholds are explicit experimental parameters and
must not be interpreted as production guarantees.
"""
from __future__ import annotations
import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from enum import Enum

class Scenario(str, Enum):
    STABLE = "stable"
    ABRUPT = "abrupt"
    GRADUAL = "gradual"
    AUTOCORRELATED = "autocorrelated"
    CONTROL_CONTAMINATION = "control_contamination"

@dataclass(frozen=True)
class DetectorConfig:
    window: int = 30
    min_samples: int = 20
    tv_threshold: float = 0.25
    alpha: float = 0.05
    cusum_threshold: float = 5.0
    change_threshold: float = 6.635

@dataclass(frozen=True)
class EpisodeResult:
    scenario: str
    detector: str
    seed: int
    alarm_at: int | None
    change_at: int | None
    false_alarm: bool
    detected: bool
    delay: int | None

def _binomial_two_sided_pvalue(successes: int, n: int, p: float) -> float:
    """Probability-ordered exact two-sided binomial p-value."""
    if n <= 0:
        return 1.0
    probs = [math.comb(n, k) * p**k * (1-p)**(n-k) for k in range(n+1)]
    observed = probs[successes]
    return min(1.0, sum(value for value in probs if value <= observed * (1 + 1e-12)))

def _pearson_pvalue(successes: int, n: int, p: float) -> float:
    expected = n * p
    other = n * (1-p)
    if expected <= 0 or other <= 0:
        return 1.0
    failures = n-successes
    statistic = (successes-expected)**2/expected + (failures-other)**2/other
    # chi-square survival function for one degree of freedom.
    return math.erfc(math.sqrt(statistic/2))

def _tv(successes: int, n: int, p: float) -> float:
    return abs(successes/n-p)

def _llr(successes: int, n: int, p0: float, p1: float) -> float:
    failures=n-successes
    return successes*math.log(p1/p0)+failures*math.log((1-p1)/(1-p0))

def _change_point_stat(values: list[int], p0: float) -> float:
    best=0.0
    n=len(values)
    for split in range(10, n-9):
        left, right=values[:split], values[split:]
        # Compare common-rate null against separate-rate alternative.
        total=sum(values)
        def log_likelihood(k, size, probability):
            probability=min(max(probability, 1e-12), 1-1e-12)
            return k*math.log(probability)+(size-k)*math.log(1-probability)
        null=log_likelihood(total,n,total/n)
        alt=log_likelihood(sum(left),len(left),sum(left)/len(left))
        alt+=log_likelihood(sum(right),len(right),sum(right)/len(right))
        best=max(best,2*(alt-null))
    return best

def _generate(seed: int, scenario: Scenario, horizon: int, change_at: int):
    rng=random.Random(seed)
    values=[]
    state=0
    for t in range(horizon):
        p=0.2
        if scenario is Scenario.ABRUPT and t>=change_at:
            p=0.5
        elif scenario is Scenario.GRADUAL and t>=change_at:
            p=0.2+0.3*min(1.0,(t-change_at+1)/20)
        elif scenario is Scenario.AUTOCORRELATED:
            if rng.random()<0.18:
                state=1-state
            values.append(state)
            continue
        elif scenario is Scenario.CONTROL_CONTAMINATION and t>=change_at:
            # Represents a control object that itself changes; it must not be
            # silently interpreted as evidence of candidate mechanism failure.
            p=0.65
        values.append(1 if rng.random()<p else 0)
    return values

def _first_alarm(values, detector, config: DetectorConfig, p0=0.2):
    cusum=0.0
    for end in range(config.min_samples, len(values)+1):
        window=values[max(0,end-config.window):end]
        n=len(window)
        successes=sum(window)
        if detector=="tv" and _tv(successes,n,p0)>config.tv_threshold:
            return end
        if detector=="pearson" and _pearson_pvalue(successes,n,p0)<config.alpha:
            return end
        if detector=="exact_binomial" and _binomial_two_sided_pvalue(successes,n,p0)<config.alpha:
            return end
        if detector=="cusum":
            # One-sided upward-shift CUSUM; reset is part of the detector.
            cusum=max(0.0,cusum+math.log(0.5/p0) if window[-1] else cusum+math.log(0.5/(1-p0)))
            if cusum>config.cusum_threshold:
                return end
        if detector=="change_point" and n>=2*config.min_samples:
            if _change_point_stat(window,p0)>config.change_threshold:
                return end
    return None

def run_benchmark(*, seeds=100, start_seed=1, horizon=100, change_at=40,
                  config: DetectorConfig=DetectorConfig()):
    if seeds<1 or horizon<2*config.min_samples or not 0<change_at<horizon:
        raise ValueError("invalid benchmark dimensions")
    detectors=("tv","pearson","exact_binomial","cusum","change_point")
    scenarios=tuple(Scenario)
    results=[]
    for scenario in scenarios:
        for offset in range(seeds):
            seed=start_seed+offset
            values=_generate(seed,scenario,horizon,change_at)
            for detector in detectors:
                alarm=_first_alarm(values,detector,config)
                has_change=scenario is not Scenario.STABLE
                false_alarm=alarm is not None and (not has_change or alarm<change_at)
                detected=alarm is not None and (not has_change or alarm>=change_at)
                delay=(alarm-change_at if detected and has_change else None)
                results.append(EpisodeResult(scenario.value,detector,seed,alarm,
                    change_at if has_change else None,false_alarm,detected,delay))
    summary={}
    for scenario in scenarios:
        for detector in detectors:
            subset=[r for r in results if r.scenario==scenario.value and r.detector==detector]
            alarms=sum(r.alarm_at is not None for r in subset)
            false=sum(r.false_alarm for r in subset)
            detected=sum(r.detected for r in subset)
            delays=[r.delay for r in subset if r.delay is not None]
            summary[f"{scenario.value}:{detector}"]={
                "episodes":len(subset),"alarm_rate":alarms/len(subset),
                "false_alarm_rate":false/len(subset),
                "detection_rate":detected/len(subset),
                "mean_detection_delay":sum(delays)/len(delays) if delays else None,
            }
    return {"config":asdict(config),"seeds":seeds,"start_seed":start_seed,
            "horizon":horizon,"change_at":change_at,
            "limitations":["synthetic binary streams only","fixed thresholds are not calibrated guarantees",
                "autocorrelation scenario is stationary Markov-like and not matched to Bernoulli baseline",
                "control contamination is not an end-to-end two-stream causal identification experiment"],
            "summary":summary}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--seeds",type=int,default=100)
    parser.add_argument("--start-seed",type=int,default=1)
    parser.add_argument("--horizon",type=int,default=100)
    parser.add_argument("--change-at",type=int,default=40)
    parser.add_argument("--json",action="store_true")
    args=parser.parse_args()
    result=run_benchmark(seeds=args.seeds,start_seed=args.start_seed,
        horizon=args.horizon,change_at=args.change_at)
    print(json.dumps(result,sort_keys=True,indent=2))
if __name__=="__main__":
    main()

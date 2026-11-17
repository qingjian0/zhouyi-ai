# Pairwise-preserving high-order necessity probe

日期：2026-11-11  
状态：可复现的穷举表达能力测试；不是模型训练或自然任务泛化结果。

## Design
Enumerate all eight assignments of three binary role variables. The target is the parity sign x1*x2*x3. Construct features using the actual LearnableSROK assignment feature map. Compare:
- unary + all pairwise features, with every integer coefficient in [-2,2] exhaustively checked (15,625 hypotheses);
- the actual third-order interaction feature.

## Result
The bounded pairwise family reaches at most 6/8 (75%); the third-order feature reaches 8/8 (100%).

## Interpretation boundary
This proves that this specific parity relation is not represented exactly by the tested unary/pairwise linear score family, while the third-order feature represents it. It does not prove the current optimizer learns the interaction from data, that higher-order terms help natural tasks, or that adding all triples is computationally worthwhile. Next experiment must test training convergence, noisy labels, held-out compositional tasks and matched compute.

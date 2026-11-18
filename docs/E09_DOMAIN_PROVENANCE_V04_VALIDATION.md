# E09 Domain Provenance v0.4 Validation Gate

The v0.4 implementation is a stacked security change on top of the authenticated
E09/E12-A6 writer chain. It is not a main-branch release.

The exact-head gate must include:

- all repository unit tests;
- observation/commit/reveal v0.4 closed-schema tests;
- trusted registry missing/revoked and cross-domain rejection tests;
- signed v2 verifier receipt tests;
- E12-A6 writer receipt consumption and ZPCM restart/replay tests;
- existing E01/E02 algorithmic baselines.

A passing CI run proves the reference implementation and tests are internally
consistent. Production readiness additionally requires a managed registry,
separate E09 authority deployment, and OS-level database access restrictions.

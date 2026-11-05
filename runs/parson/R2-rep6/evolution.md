# Strategy evolution

- iter 1: acc=0.503 novelty=15 cap_mass=0.051 score=77.5 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 2: build rejected (disallowed import: random) -> rollback
- iter 3: acc=0.523 novelty=18 cap_mass=0.049 score=76.1 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: acc=0.551 novelty=12 cap_mass=0.021 score=76.4 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 5: acc=0.529 novelty=21 cap_mass=0.016 score=78.3 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

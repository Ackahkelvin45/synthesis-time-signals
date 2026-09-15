# Strategy evolution

- iter 1: build rejected (disallowed import: random) -> rollback
- iter 2: build rejected (dunder attribute access: __str__) -> rollback
- iter 3: gated at acc=0.00; full run skipped
- iter 4: gated at acc=0.00; full run skipped
- iter 5: acc=0.246 novelty=14 cap_mass=0.0 score=174.0 crash=False deviations=[] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))

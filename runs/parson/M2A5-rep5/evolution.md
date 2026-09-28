# Strategy evolution

- iter 1: build rejected (dunder attribute access: __str__) -> rollback
- iter 2: acc=0.169 novelty=13 cap_mass=0.364 score=60.3 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))
- iter 3: build rejected (import: AttributeError: module 'hypothesis.strategies' has no attribute 'frequency') -> rollback
- iter 4: acc=0.163 novelty=12 cap_mass=0.509 score=62.2 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))
- iter 5: acc=0.166 novelty=19 cap_mass=0.172 score=62.4 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))

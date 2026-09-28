# Strategy evolution

- iter 1: build rejected (import: AttributeError: module 'hypothesis.strategies' has no attribute 'digits') -> rollback
- iter 2: acc=0.289 novelty=29 cap_mass=0.267 score=79.3 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))
- iter 3: acc=0.274 novelty=22 cap_mass=0.219 score=71.4 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))
- iter 4: acc=0.234 novelty=23 cap_mass=0.159 score=71.2 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))
- iter 5: acc=0.194 novelty=21 cap_mass=0.206 score=70.1 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))

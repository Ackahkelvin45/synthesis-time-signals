# Strategy evolution

- iter 1: build rejected (import: NameError: name '_array' is not defined) -> rollback
- iter 2: acc=0.111 novelty=2 cap_mass=0.0 score=22.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))
- iter 3: acc=0.389 novelty=3 cap_mass=0.0 score=23.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))
- iter 4: acc=0.147 novelty=4 cap_mass=0.0 score=34.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))
- iter 5: acc=0.05 novelty=1 cap_mass=0.0 score=16.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))

# Strategy evolution

- iter 1: build rejected (strategy does not parse: unterminated string literal (detected at line 120) (<unknown>, line 120)) -> rollback
- iter 2: acc=0.15 novelty=4 cap_mass=0.0 score=29.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))
- iter 3: acc=0.205 novelty=14 cap_mass=0.0 score=54.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))
- iter 4: acc=0.18 novelty=8 cap_mass=0.0 score=53.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))
- iter 5: acc=0.146 novelty=6 cap_mass=0.0 score=36.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))

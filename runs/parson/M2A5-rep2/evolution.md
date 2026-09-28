# Strategy evolution

- iter 1: build rejected (strategy does not parse: unterminated string literal (detected at line 27); perhaps you escaped the end quote? (<unknown>, line 27)) -> rollback
- iter 2: acc=0.28 novelty=7 cap_mass=0.0 score=42.0 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))
- iter 3: acc=0.329 novelty=8 cap_mass=0.0 score=43.0 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))
- iter 4: acc=0.263 novelty=6 cap_mass=0.0 score=41.0 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))
- iter 5: acc=0.346 novelty=9 cap_mass=0.0 score=44.0 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))

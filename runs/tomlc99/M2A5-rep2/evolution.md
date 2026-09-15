# Strategy evolution

- iter 1: build rejected (strategy does not parse: unterminated string literal (detected at line 65) (<unknown>, line 65)) -> rollback
- iter 2: build rejected (dunder attribute access: __format__) -> rollback
- iter 3: build rejected (disallowed import: random) -> rollback
- iter 4: acc=0.406 novelty=18 cap_mass=0.0 score=118.0 crash=False deviations=[] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))
- iter 5: acc=0.457 novelty=19 cap_mass=0.0 score=99.0 crash=False deviations=[] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))

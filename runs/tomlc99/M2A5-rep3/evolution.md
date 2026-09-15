# Strategy evolution

- iter 1: build rejected (import: TypeError: deferred() missing 1 required positional argument: 'definition') -> rollback
- iter 2: build rejected (strategy does not parse: unterminated string literal (detected at line 55) (<unknown>, line 55)) -> rollback
- iter 3: build rejected (strategy does not parse: invalid syntax (<unknown>, line 248)) -> rollback
- iter 4: gated at acc=0.02; full run skipped
- iter 5: acc=0.055 novelty=10 cap_mass=0.077 score=166.5 crash=True deviations=[] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))

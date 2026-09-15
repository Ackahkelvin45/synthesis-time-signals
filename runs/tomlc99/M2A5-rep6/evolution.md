# Strategy evolution

- iter 1: gated at acc=0.00; full run skipped
- iter 2: acc=0.114 novelty=20 cap_mass=0.0 score=125.0 crash=False deviations=[] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))
- iter 3: build rejected (strategy does not parse: closing parenthesis ')' does not match opening parenthesis '{' (<unknown>, line 89)) -> rollback
- iter 4: acc=0.109 novelty=27 cap_mass=0.0 score=152.0 crash=False deviations=[] -> next: improve_strategy (make it a better fuzzer for this grammar (no run feedback is provided))
- iter 5: build rejected (strategy does not parse: closing parenthesis ')' does not match opening parenthesis '{' (<unknown>, line 89)) -> rollback

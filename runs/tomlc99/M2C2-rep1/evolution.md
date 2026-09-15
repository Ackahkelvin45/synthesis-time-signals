# Strategy evolution

- iter 1: build rejected (strategy does not parse: unterminated string literal (detected at line 201) (<unknown>, line 201)) -> rollback
- iter 2: build rejected (disallowed import: random) -> rollback
- iter 3: build rejected (strategy does not parse: cannot use assignment expressions with attribute (<unknown>, line 198)) -> rollback
- iter 4: gated at acc=0.00; full run skipped
- iter 5: acc=0.309 novelty=48 cap_mass=0.0 score=198.0 crash=False deviations=[] -> next: add_or_upweight_production (integer)

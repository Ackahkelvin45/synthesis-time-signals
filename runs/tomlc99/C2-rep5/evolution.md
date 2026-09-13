# Strategy evolution

- iter 1: build rejected (import: RecursionError: maximum recursion depth exceeded) -> rollback
- iter 2: acc=0.189 novelty=19 cap_mass=0.015 score=144.3 crash=False deviations=[] -> next: add_or_upweight_production (floating_point)
- iter 3: acc=0.251 novelty=24 cap_mass=0.023 score=189.5 crash=False deviations=[] -> next: add_or_upweight_production (string)
- iter 4: acc=0.411 novelty=43 cap_mass=0.021 score=213.4 crash=False deviations=[] -> next: add_or_upweight_production (bool_)
- iter 5: build rejected (strategy does not parse: unterminated string literal (detected at line 814) (<unknown>, line 814)) -> rollback

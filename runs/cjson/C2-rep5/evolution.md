# Strategy evolution

- iter 1: build rejected (import: NameError: name '_pair' is not defined) -> rollback
- iter 2: acc=0.337 novelty=8 cap_mass=0.025 score=48.5 crash=False deviations=['deep_nesting'] -> next: add_or_upweight_production (true)
- iter 3: acc=0.397 novelty=10 cap_mass=0.014 score=55.3 crash=False deviations=['deep_nesting'] -> next: add_or_upweight_production (true)
- iter 4: acc=0.354 novelty=9 cap_mass=0.024 score=54.5 crash=False deviations=['deep_nesting'] -> next: add_or_upweight_production (false)
- iter 5: acc=0.397 novelty=12 cap_mass=0.014 score=62.3 crash=False deviations=['deep_nesting'] -> next: generate_nesting_toward_cap (target depth 700-950)

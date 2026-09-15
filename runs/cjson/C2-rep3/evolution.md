# Strategy evolution

- iter 1: build rejected (import: NameError: name '_obj_body_with' is not defined) -> rollback
- iter 2: acc=0.217 novelty=10 cap_mass=0.026 score=55.5 crash=False deviations=['deep_nesting'] -> next: add_or_upweight_production (pair)
- iter 3: acc=0.183 novelty=9 cap_mass=0.0 score=54.0 crash=False deviations=['deep_nesting'] -> next: add_or_upweight_production (pair)
- iter 4: acc=0.263 novelty=9 cap_mass=0.033 score=59.7 crash=False deviations=['deep_nesting'] -> next: generate_nesting_toward_cap (target depth 700-950)
- iter 5: acc=0.206 novelty=8 cap_mass=0.0 score=58.0 crash=False deviations=['deep_nesting'] -> next: generate_nesting_toward_cap (target depth 700-950)

# Strategy evolution

- iter 1: acc=0.55 novelty=13 cap_mass=0.0 score=53.0 crash=False deviations=['deep_nesting'] -> next: add_or_upweight_production (true)
- iter 2: acc=0.543 novelty=14 cap_mass=0.0 score=59.0 crash=False deviations=['deep_nesting'] -> next: add_or_upweight_production (false)
- iter 3: acc=0.509 novelty=10 cap_mass=0.0 score=55.0 crash=False deviations=['deep_nesting'] -> next: add_or_upweight_production (false)
- iter 4: acc=0.583 novelty=17 cap_mass=0.005 score=67.1 crash=False deviations=['deep_nesting'] -> next: generate_nesting_toward_cap (target depth 700-950)
- iter 5: acc=0.543 novelty=9 cap_mass=0.0 score=54.0 crash=False deviations=['deep_nesting'] REGRESSION->rollback next: revert_last_edit (score 54.0 < best 67.1)

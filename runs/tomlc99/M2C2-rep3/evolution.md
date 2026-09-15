# Strategy evolution

- iter 1: build rejected (disallowed import: random) -> rollback
- iter 2: build rejected (disallowed import: random) -> rollback
- iter 3: acc=0.062 novelty=11 cap_mass=0.0 score=106.0 crash=False deviations=[] -> next: add_or_upweight_production (integer)
- iter 4: acc=0.054 novelty=10 cap_mass=0.0 score=95.0 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 95.0 < best 106.0)
- iter 5: acc=0.083 novelty=15 cap_mass=0.0 score=130.0 crash=False deviations=[] -> next: add_or_upweight_production (integer)

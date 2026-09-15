# Strategy evolution

- iter 1: acc=0.215 novelty=30 cap_mass=0.0 score=155.0 crash=False deviations=[] -> next: add_or_upweight_production (integer)
- iter 2: build rejected (import: NameError: name '__CONTROL_CHARS' is not defined) -> rollback
- iter 3: acc=0.2 novelty=31 cap_mass=0.0 score=136.0 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 136.0 < best 155.0)
- iter 4: acc=0.237 novelty=35 cap_mass=0.0 score=140.0 crash=False deviations=[] -> next: add_or_upweight_production (integer)
- iter 5: acc=0.277 novelty=39 cap_mass=0.0 score=169.0 crash=False deviations=[] -> next: add_or_upweight_production (string)

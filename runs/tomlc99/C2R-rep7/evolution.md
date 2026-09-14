# Strategy evolution

- iter 1: build rejected (dunder attribute access: __iter__) -> rollback
- iter 2: acc=0.669 novelty=60 cap_mass=0.38 score=242.6 crash=False deviations=[] -> next: add_or_upweight_production (ML_BASIC_STRING)
- iter 3: acc=0.586 novelty=49 cap_mass=0.405 score=237.1 crash=False deviations=[] -> next: add_or_upweight_production (bool_)
- iter 4: acc=0.583 novelty=53 cap_mass=0.426 score=226.5 crash=False deviations=[] -> next: add_or_upweight_production (bool_)
- iter 5: acc=0.629 novelty=44 cap_mass=0.486 score=208.7 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 208.7 < best 242.6)

# Strategy evolution

- iter 1: acc=0.472 novelty=39 cap_mass=0.391 score=231.8 crash=False deviations=[] -> next: add_or_upweight_production (ML_BASIC_STRING)
- iter 2: acc=0.359 novelty=34 cap_mass=0.16 score=207.2 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 207.2 < best 231.8)
- iter 3: acc=0.421 novelty=35 cap_mass=0.387 score=227.7 crash=False deviations=[] -> next: add_or_upweight_production (ML_BASIC_STRING)
- iter 4: acc=0.633 novelty=21 cap_mass=0.11 score=183.2 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 183.2 < best 231.8)
- iter 5: acc=0.423 novelty=36 cap_mass=0.466 score=225.3 crash=False deviations=[] -> next: add_or_upweight_production (bool_)

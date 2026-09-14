# Strategy evolution

- iter 1: acc=0.577 novelty=37 cap_mass=0.22 score=211.4 crash=False deviations=[] -> next: add_or_upweight_production (bool_)
- iter 2: acc=0.523 novelty=45 cap_mass=0.224 score=244.5 crash=False deviations=[] -> next: add_or_upweight_production (ML_BASIC_STRING)
- iter 3: acc=0.46 novelty=48 cap_mass=0.174 score=206.5 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 206.5 < best 244.5)
- iter 4: acc=0.546 novelty=33 cap_mass=0.257 score=188.1 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 188.1 < best 244.5)
- iter 5: acc=0.506 novelty=44 cap_mass=0.266 score=214.3 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 214.3 < best 244.5)

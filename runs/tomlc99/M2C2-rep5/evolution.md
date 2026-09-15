# Strategy evolution

- iter 1: acc=0.227 novelty=4 cap_mass=0.0 score=59.0 crash=False deviations=[] -> next: add_or_upweight_production (key_value)
- iter 2: acc=0.211 novelty=6 cap_mass=0.0 score=91.0 crash=False deviations=[] -> next: add_or_upweight_production (dotted_key)
- iter 3: acc=0.203 novelty=4 cap_mass=0.0 score=29.0 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 29.0 < best 91.0)
- iter 4: acc=0.191 novelty=4 cap_mass=0.0 score=59.0 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 59.0 < best 91.0)
- iter 5: acc=0.22 novelty=4 cap_mass=0.0 score=29.0 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 29.0 < best 91.0)

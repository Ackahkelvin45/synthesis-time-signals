# Strategy evolution

- iter 1: gated at acc=0.00; full run skipped
- iter 2: acc=0.415 novelty=33 cap_mass=0.228 score=237.6 crash=False deviations=[] -> next: add_or_upweight_production (INF)
- iter 3: acc=0.427 novelty=37 cap_mass=0.168 score=240.4 crash=False deviations=[] -> next: add_or_upweight_production (FLOAT)
- iter 4: acc=0.682 novelty=29 cap_mass=0.063 score=200.3 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 200.3 < best 240.4)
- iter 5: acc=0.406 novelty=30 cap_mass=0.155 score=223.1 crash=False deviations=[] -> next: add_or_upweight_production (FLOAT)

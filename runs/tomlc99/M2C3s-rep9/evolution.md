# Strategy evolution

- iter 1: acc=0.403 novelty=40 cap_mass=0.0 score=57.6 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 57.6%; reach parser code the current inputs never execute)
- iter 2: acc=0.262 novelty=35 cap_mass=0.0 score=47.9 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 47.9 < best 57.6)
- iter 3: acc=0.274 novelty=35 cap_mass=0.0 score=57.8 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 57.8%; reach parser code the current inputs never execute)
- iter 4: acc=0.274 novelty=33 cap_mass=0.0 score=61.8 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 61.8%; reach parser code the current inputs never execute)
- iter 5: acc=0.246 novelty=36 cap_mass=0.0 score=59.2 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 59.2%; reach parser code the current inputs never execute)

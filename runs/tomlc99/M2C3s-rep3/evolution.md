# Strategy evolution

- iter 1: acc=0.106 novelty=16 cap_mass=0.0 score=73.4 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 73.4%; reach parser code the current inputs never execute)
- iter 2: acc=0.111 novelty=12 cap_mass=0.0 score=74.3 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 74.3%; reach parser code the current inputs never execute)
- iter 3: acc=0.069 novelty=10 cap_mass=0.0 score=65.6 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 65.6 < best 74.3)
- iter 4: acc=0.146 novelty=19 cap_mass=0.0 score=74.2 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 74.2%; reach parser code the current inputs never execute)
- iter 5: acc=0.137 novelty=16 cap_mass=0.0 score=73.3 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 73.3%; reach parser code the current inputs never execute)

# Strategy evolution

- iter 1: acc=0.117 novelty=11 cap_mass=0.0 score=55.8 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 55.8%; reach parser code the current inputs never execute)
- iter 2: acc=0.077 novelty=12 cap_mass=0.0 score=54.5 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 54.5%; reach parser code the current inputs never execute)
- iter 3: acc=0.123 novelty=18 cap_mass=0.0 score=55.2 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 55.2%; reach parser code the current inputs never execute)
- iter 4: acc=0.057 novelty=8 cap_mass=0.0 score=57.9 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 57.9%; reach parser code the current inputs never execute)
- iter 5: acc=0.065 novelty=9 cap_mass=0.0 score=41.7 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 41.7 < best 57.9)

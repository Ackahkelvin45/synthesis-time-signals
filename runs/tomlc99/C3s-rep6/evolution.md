# Strategy evolution

- iter 1: acc=0.491 novelty=85 cap_mass=0.0 score=72.9 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 72.9%; reach parser code the current inputs never execute)
- iter 2: acc=0.389 novelty=65 cap_mass=0.0 score=73.8 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 73.8%; reach parser code the current inputs never execute)
- iter 3: acc=0.551 novelty=81 cap_mass=0.0 score=69.1 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 69.1%; reach parser code the current inputs never execute)
- iter 4: acc=0.651 novelty=73 cap_mass=0.0 score=70.1 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 70.1%; reach parser code the current inputs never execute)
- iter 5: acc=0.654 novelty=69 cap_mass=0.0 score=63.4 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 63.4 < best 73.8)

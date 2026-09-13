# Strategy evolution

- iter 1: build rejected (dunder attribute access: __class__) -> rollback
- iter 2: acc=0.497 novelty=52 cap_mass=0.523 score=69.4 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 69.4%; reach parser code the current inputs never execute)
- iter 3: acc=0.52 novelty=58 cap_mass=0.363 score=75.2 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 75.2%; reach parser code the current inputs never execute)
- iter 4: acc=0.594 novelty=61 cap_mass=0.327 score=72.6 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 72.6%; reach parser code the current inputs never execute)
- iter 5: build rejected (strategy does not parse: unterminated string literal (detected at line 860) (<unknown>, line 860)) -> rollback

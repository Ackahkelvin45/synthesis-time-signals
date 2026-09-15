# Strategy evolution

- iter 1: build rejected (disallowed import: random) -> rollback
- iter 2: build rejected (disallowed name: locals) -> rollback
- iter 3: build rejected (disallowed import: random) -> rollback
- iter 4: acc=0.084 novelty=10 cap_mass=0.0 score=65.1 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 65.1%; reach parser code the current inputs never execute)
- iter 5: acc=0.04 novelty=3 cap_mass=0.0 score=59.3 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 59.3%; reach parser code the current inputs never execute)

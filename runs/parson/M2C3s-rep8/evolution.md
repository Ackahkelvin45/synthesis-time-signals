# Strategy evolution

- iter 1: build rejected (import: TypeError: characters() takes 0 positional arguments but 1 was given) -> rollback
- iter 2: acc=0.392 novelty=8 cap_mass=0.765 score=67.4 crash=False deviations=['duplicate_keys'] -> next: increase_branch_coverage (branch coverage is 67.4%; reach parser code the current inputs never execute)
- iter 3: acc=0.377 novelty=12 cap_mass=0.742 score=66.3 crash=False deviations=['duplicate_keys'] -> next: increase_branch_coverage (branch coverage is 66.3%; reach parser code the current inputs never execute)
- iter 4: acc=0.357 novelty=9 cap_mass=0.784 score=69.3 crash=False deviations=['duplicate_keys'] -> next: increase_branch_coverage (branch coverage is 69.3%; reach parser code the current inputs never execute)
- iter 5: acc=0.354 novelty=10 cap_mass=0.79 score=66.8 crash=False deviations=['duplicate_keys'] -> next: increase_branch_coverage (branch coverage is 66.8%; reach parser code the current inputs never execute)

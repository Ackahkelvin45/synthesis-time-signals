# Strategy evolution

- iter 1: acc=0.474 novelty=16 cap_mass=0.133 score=73.9 crash=False deviations=['duplicate_keys'] -> next: increase_branch_coverage (branch coverage is 73.9%; reach parser code the current inputs never execute)
- iter 2: acc=0.561 novelty=20 cap_mass=0.088 score=77.2 crash=False deviations=['duplicate_keys'] -> next: increase_branch_coverage (branch coverage is 77.2%; reach parser code the current inputs never execute)
- iter 3: acc=0.455 novelty=19 cap_mass=0.097 score=78.5 crash=False deviations=['duplicate_keys'] -> next: increase_branch_coverage (branch coverage is 78.5%; reach parser code the current inputs never execute)
- iter 4: acc=0.493 novelty=18 cap_mass=0.064 score=74.7 crash=False deviations=['duplicate_keys'] -> next: increase_branch_coverage (branch coverage is 74.7%; reach parser code the current inputs never execute)
- iter 5: build rejected (strategy does not parse: invalid syntax (<unknown>, line 1)) -> rollback

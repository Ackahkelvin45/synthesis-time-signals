# Strategy evolution

- iter 1: build rejected (import: RecursionError: maximum recursion depth exceeded) -> rollback
- iter 2: acc=0.435 novelty=35 cap_mass=0.274 score=66.9 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 66.9%; reach parser code the current inputs never execute)
- iter 3: acc=0.434 novelty=43 cap_mass=0.285 score=69.0 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 69.0%; reach parser code the current inputs never execute)
- iter 4: acc=0.529 novelty=74 cap_mass=0.114 score=70.4 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 70.4%; reach parser code the current inputs never execute)
- iter 5: build rejected (strategy does not parse: invalid syntax (<unknown>, line 1)) -> rollback

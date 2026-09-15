# Strategy evolution

- iter 1: build rejected (import: TypeError: can only concatenate str (not "LazyStrategy") to str) -> rollback
- iter 2: acc=0.126 novelty=19 cap_mass=0.0 score=65.1 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 65.1%; reach parser code the current inputs never execute)
- iter 3: acc=0.117 novelty=13 cap_mass=0.0 score=72.6 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 72.6%; reach parser code the current inputs never execute)
- iter 4: acc=0.097 novelty=15 cap_mass=0.0 score=51.4 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 51.4 < best 72.6)
- iter 5: acc=0.183 novelty=22 cap_mass=0.0 score=47.0 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 47.0 < best 72.6)

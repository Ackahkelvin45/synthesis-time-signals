# Strategy evolution

- iter 1: acc=0.306 novelty=46 cap_mass=0.318 score=73.7 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 73.7%; reach parser code the current inputs never execute)
- iter 2: acc=0.3 novelty=35 cap_mass=0.352 score=67.5 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 67.5%; reach parser code the current inputs never execute)
- iter 3: acc=0.366 novelty=40 cap_mass=0.189 score=66.3 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 66.3 < best 73.7)
- iter 4: acc=0.314 novelty=30 cap_mass=0.409 score=70.0 crash=False deviations=[] -> next: increase_branch_coverage (branch coverage is 70.0%; reach parser code the current inputs never execute)
- iter 5: acc=0.38 novelty=34 cap_mass=0.271 score=64.8 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 64.8 < best 73.7)

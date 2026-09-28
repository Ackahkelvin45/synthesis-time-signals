# Strategy evolution

- iter 1: acc=0.129 novelty=8 cap_mass=0.511 score=69.8 crash=False deviations=['duplicate_keys'] -> next: increase_branch_coverage (branch coverage is 69.8%; reach parser code the current inputs never execute)
- iter 2: acc=0.177 novelty=8 cap_mass=0.484 score=72.0 crash=False deviations=['duplicate_keys'] -> next: increase_branch_coverage (branch coverage is 72.0%; reach parser code the current inputs never execute)
- iter 3: acc=0.114 novelty=5 cap_mass=0.6 score=69.0 crash=False deviations=['duplicate_keys'] -> next: increase_branch_coverage (branch coverage is 69.0%; reach parser code the current inputs never execute)
- iter 4: acc=0.103 novelty=6 cap_mass=0.583 score=63.6 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 63.6 < best 72.0)
- iter 5: acc=0.123 novelty=6 cap_mass=0.581 score=66.6 crash=False deviations=['duplicate_keys'] -> next: increase_branch_coverage (branch coverage is 66.6%; reach parser code the current inputs never execute)

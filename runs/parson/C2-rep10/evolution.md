# Strategy evolution

- iter 1: acc=0.627 novelty=25 cap_mass=0.0 score=75.0 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)
- iter 2: acc=0.714 novelty=36 cap_mass=0.036 score=86.7 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)
- iter 3: acc=0.609 novelty=27 cap_mass=0.019 score=77.4 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 77.4 < best 86.7)
- iter 4: acc=0.666 novelty=31 cap_mass=0.017 score=81.3 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)
- iter 5: acc=0.691 novelty=34 cap_mass=0.021 score=84.4 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)

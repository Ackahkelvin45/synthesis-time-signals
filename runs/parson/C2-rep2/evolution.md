# Strategy evolution

- iter 1: acc=0.6 novelty=24 cap_mass=0.019 score=74.4 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)
- iter 2: acc=0.717 novelty=16 cap_mass=0.024 score=66.5 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 66.5 < best 74.4)
- iter 3: acc=0.617 novelty=14 cap_mass=0.023 score=64.5 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 64.5 < best 74.4)
- iter 4: acc=0.566 novelty=24 cap_mass=0.015 score=74.3 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)
- iter 5: acc=0.497 novelty=28 cap_mass=0.029 score=78.6 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)

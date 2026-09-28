# Strategy evolution

- iter 1: acc=0.431 novelty=11 cap_mass=0.0 score=61.0 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)
- iter 2: acc=0.471 novelty=15 cap_mass=0.0 score=60.0 crash=False deviations=['duplicate_keys'] -> next: add_or_upweight_production (null)
- iter 3: acc=0.486 novelty=16 cap_mass=0.0 score=66.0 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)
- iter 4: acc=0.417 novelty=19 cap_mass=0.0 score=69.0 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)
- iter 5: acc=0.451 novelty=12 cap_mass=0.0 score=62.0 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 62.0 < best 69.0)

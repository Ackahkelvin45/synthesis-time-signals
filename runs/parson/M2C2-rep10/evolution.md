# Strategy evolution

- iter 1: acc=0.06 novelty=6 cap_mass=0.0 score=36.0 crash=False deviations=['duplicate_keys'] -> next: add_or_upweight_production (NUMBER)
- iter 2: acc=0.08 novelty=7 cap_mass=0.0 score=47.0 crash=False deviations=['duplicate_keys'] -> next: add_or_upweight_production (false)
- iter 3: acc=0.08 novelty=5 cap_mass=0.0 score=40.0 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 40.0 < best 47.0)
- iter 4: acc=0.063 novelty=4 cap_mass=0.0 score=39.0 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 39.0 < best 47.0)
- iter 5: acc=0.066 novelty=6 cap_mass=0.0 score=41.0 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 41.0 < best 47.0)

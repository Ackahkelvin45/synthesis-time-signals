# Strategy evolution

- iter 1: build rejected (disallowed import: re) -> rollback
- iter 2: acc=0.369 novelty=10 cap_mass=0.531 score=55.6 crash=False deviations=['duplicate_keys'] -> next: add_or_upweight_production (true)
- iter 3: acc=0.357 novelty=12 cap_mass=0.496 score=61.9 crash=False deviations=['duplicate_keys'] -> next: add_or_upweight_production (true)
- iter 4: acc=0.32 novelty=13 cap_mass=0.527 score=63.5 crash=False deviations=['duplicate_keys'] -> next: add_or_upweight_production (true)
- iter 5: acc=0.306 novelty=8 cap_mass=0.645 score=55.9 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 55.9 < best 63.5)

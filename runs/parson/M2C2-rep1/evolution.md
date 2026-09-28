# Strategy evolution

- iter 1: acc=0.142 novelty=7 cap_mass=0.0 score=37.0 crash=False deviations=['duplicate_keys'] -> next: add_or_upweight_production (NUMBER)
- iter 2: acc=0.134 novelty=7 cap_mass=0.0 score=42.0 crash=False deviations=['duplicate_keys'] -> next: add_or_upweight_production (true)
- iter 3: acc=0.1 novelty=8 cap_mass=0.0 score=43.0 crash=False deviations=['duplicate_keys'] -> next: add_or_upweight_production (true)
- iter 4: acc=0.103 novelty=8 cap_mass=0.0 score=43.0 crash=False deviations=['duplicate_keys'] -> next: add_or_upweight_production (true)
- iter 5: acc=0.089 novelty=5 cap_mass=0.0 score=30.0 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 30.0 < best 43.0)

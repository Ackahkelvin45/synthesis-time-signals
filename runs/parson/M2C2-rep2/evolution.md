# Strategy evolution

- iter 1: acc=0.24 novelty=11 cap_mass=0.012 score=56.2 crash=False deviations=['duplicate_keys'] -> next: add_or_upweight_production (null)
- iter 2: acc=0.189 novelty=14 cap_mass=0.0 score=64.0 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)
- iter 3: acc=0.209 novelty=17 cap_mass=0.11 score=69.2 crash=False deviations=['duplicate_keys'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)
- iter 4: acc=0.22 novelty=13 cap_mass=0.078 score=49.6 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 49.6 < best 69.2)
- iter 5: acc=0.16 novelty=8 cap_mass=0.0 score=53.0 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 53.0 < best 69.2)

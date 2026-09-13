# Strategy evolution

- iter 1: acc=0.189 novelty=19 cap_mass=0.076 score=70.5 crash=False deviations=['duplicate_keys'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)
- iter 2: acc=0.24 novelty=20 cap_mass=0.012 score=70.2 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)
- iter 3: acc=0.251 novelty=18 cap_mass=0.023 score=63.5 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 63.5 < best 70.5)
- iter 4: acc=0.171 novelty=21 cap_mass=0.05 score=72.0 crash=False deviations=['duplicate_keys'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)
- iter 5: acc=0.217 novelty=18 cap_mass=0.0 score=63.0 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 63.0 < best 72.0)

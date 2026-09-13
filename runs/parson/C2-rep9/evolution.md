# Strategy evolution

- iter 1: acc=0.466 novelty=20 cap_mass=0.025 score=70.5 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)
- iter 2: acc=0.437 novelty=11 cap_mass=0.092 score=62.8 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 62.8 < best 70.5)
- iter 3: acc=0.443 novelty=19 cap_mass=0.077 score=70.5 crash=False deviations=['duplicate_keys'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)
- iter 4: acc=0.603 novelty=18 cap_mass=0.005 score=68.1 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)
- iter 5: acc=0.54 novelty=25 cap_mass=0.101 score=77.0 crash=False deviations=['duplicate_keys'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)

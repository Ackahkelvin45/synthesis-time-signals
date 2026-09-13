# Strategy evolution

- iter 1: acc=0.557 novelty=20 cap_mass=0.133 score=72.7 crash=False deviations=['duplicate_keys'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)
- iter 2: acc=0.443 novelty=28 cap_mass=0.161 score=81.2 crash=False deviations=['duplicate_keys'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)
- iter 3: acc=0.351 novelty=23 cap_mass=0.098 score=70.0 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 70.0 < best 81.2)
- iter 4: acc=0.337 novelty=19 cap_mass=0.136 score=71.7 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 71.7 < best 81.2)
- iter 5: acc=0.451 novelty=21 cap_mass=0.108 score=73.2 crash=False deviations=['duplicate_keys'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)

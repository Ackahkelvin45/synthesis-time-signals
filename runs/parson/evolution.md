# Strategy evolution

- iter 1: gated at acc=0.00; full run skipped
- iter 2: gated at acc=0.00; full run skipped
- iter 3: acc=0.38 novelty=19 cap_mass=0.068 score=55.4 crash=False deviations=['duplicate_keys'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)
- iter 4: acc=0.363 novelty=21 cap_mass=0.031 score=56.6 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)
- iter 5: acc=0.36 novelty=13 cap_mass=0.016 score=43.3 crash=False deviations=['duplicate_keys'] REGRESSION->rollback next: revert_last_edit (score 43.3 < best 56.6)

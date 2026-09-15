# Strategy evolution

- iter 1: acc=0.243 novelty=8 cap_mass=0.0 score=108.0 crash=False deviations=[] -> next: add_or_upweight_production (dotted_key)
- iter 2: gated at acc=0.00; full run skipped
- iter 3: gated at acc=0.00; full run skipped
- iter 4: acc=0.123 novelty=5 cap_mass=0.0 score=75.0 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 75.0 < best 108.0)
- iter 5: acc=0.28 novelty=10 cap_mass=0.0 score=85.0 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 85.0 < best 108.0)

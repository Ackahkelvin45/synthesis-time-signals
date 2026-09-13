# Strategy evolution

- iter 1: acc=0.211 novelty=4 cap_mass=0.0 score=29.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 2: build rejected (import: NameError: name '_whitespace' is not defined) -> rollback
- iter 3: acc=0.105 novelty=2 cap_mass=0.0 score=22.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 4: build rejected (import: NameError: name '_whitespace_placeholder' is not defined) -> rollback
- iter 5: acc=0.074 novelty=6 cap_mass=0.0 score=36.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)

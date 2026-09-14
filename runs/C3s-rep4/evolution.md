# Strategy evolution

- iter 1: build rejected (import: NameError: name '_array' is not defined) -> rollback
- iter 2: acc=0.5 novelty=6 cap_mass=0.0 score=57.8 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 3: acc=0.105 novelty=2 cap_mass=0.0 score=59.1 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 4: acc=0.176 novelty=3 cap_mass=0.0 score=55.5 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 5: acc=0.12 novelty=3 cap_mass=0.0 score=65.8 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)

# Strategy evolution

- iter 1: acc=0.114 novelty=4 cap_mass=0.0 score=51.7 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 2: acc=0.083 novelty=3 cap_mass=0.0 score=53.2 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 3: acc=0.094 novelty=2 cap_mass=0.0 score=55.9 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 4: acc=0.05 novelty=2 cap_mass=0.0 score=56.5 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 5: build rejected (strategy does not parse: invalid syntax (<unknown>, line 1)) -> rollback

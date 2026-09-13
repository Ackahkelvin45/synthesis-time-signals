# Strategy evolution

- iter 1: acc=0.25 novelty=5 cap_mass=0.0 score=40.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 2: gated at acc=0.04; full run skipped
- iter 3: acc=0.417 novelty=5 cap_mass=0.0 score=30.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 4: acc=0.444 novelty=5 cap_mass=0.0 score=30.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 5: acc=0.538 novelty=5 cap_mass=0.0 score=35.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)

# Strategy evolution

- iter 1: build rejected (strategy does not parse: unterminated string literal (detected at line 10) (<unknown>, line 10)) -> rollback
- iter 2: acc=0.093 novelty=4 cap_mass=0.0 score=52.1 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 3: acc=0.25 novelty=4 cap_mass=0.0 score=52.3 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 4: acc=0.136 novelty=2 cap_mass=0.0 score=52.1 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 5: acc=0.292 novelty=3 cap_mass=0.0 score=52.1 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)

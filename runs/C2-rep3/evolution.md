# Strategy evolution

- iter 1: acc=0.226 novelty=6 cap_mass=0.0 score=41.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 2: acc=0.364 novelty=4 cap_mass=0.0 score=29.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 3: build rejected (strategy does not parse: unterminated string literal (detected at line 557) (<unknown>, line 557)) -> rollback
- iter 4: acc=0.286 novelty=2 cap_mass=0.0 score=17.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 5: acc=0.333 novelty=4 cap_mass=0.0 score=29.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)

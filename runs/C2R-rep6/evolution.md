# Strategy evolution

- iter 1: acc=0.25 novelty=4 cap_mass=0.0 score=29.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 2: acc=0.263 novelty=5 cap_mass=0.0 score=35.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 3: acc=0.067 novelty=8 cap_mass=0.0 score=43.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 4: acc=0.211 novelty=3 cap_mass=0.0 score=23.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: revert_last_edit (acceptance 0.067->0.211 but novelty 8->3 (quiet failure))
- iter 5: acc=0.212 novelty=4 cap_mass=0.0 score=29.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)

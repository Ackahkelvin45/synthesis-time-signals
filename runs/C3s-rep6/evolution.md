# Strategy evolution

- iter 1: build rejected (import: NameError: name '_obj_member_with' is not defined) -> rollback
- iter 2: acc=0.095 novelty=2 cap_mass=0.0 score=38.8 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 3: acc=0.14 novelty=3 cap_mass=0.0 score=52.1 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 4: acc=0.118 novelty=2 cap_mass=0.0 score=39.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 5: acc=0.167 novelty=3 cap_mass=0.0 score=31.2 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)

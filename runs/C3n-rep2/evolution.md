# Strategy evolution

- iter 1: build rejected (import: TypeError: 'OneOfStrategy' object is not callable) -> rollback
- iter 2: build rejected (import: TypeError: unsupported operand type(s) for +: 'LazyStrategy' and 'LazyStrategy') -> rollback
- iter 3: acc=0.101 novelty=4 cap_mass=0.0 score=63.5 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 4: acc=0.068 novelty=4 cap_mass=0.0 score=62.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 5: acc=0.143 novelty=2 cap_mass=0.0 score=40.7 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)

# Strategy evolution

- iter 1: build rejected (import: TypeError: _top() missing 1 required positional argument: 'draw') -> rollback
- iter 2: build rejected (import: AttributeError: 'function' object has no attribute 'calc_is_cacheable') -> rollback
- iter 3: build rejected (import: NameError: name '_obj' is not defined) -> rollback
- iter 4: acc=0.055 novelty=9 cap_mass=0.0 score=54.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 5: acc=0.06 novelty=5 cap_mass=0.0 score=35.0 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)

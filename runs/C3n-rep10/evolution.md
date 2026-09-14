# Strategy evolution

- iter 1: build rejected (import: NameError: name '_obj_with' is not defined) -> rollback
- iter 2: acc=0.304 novelty=5 cap_mass=0.0 score=49.2 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 3: acc=0.16 novelty=4 cap_mass=0.0 score=47.7 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 4: acc=0.138 novelty=2 cap_mass=0.0 score=40.3 crash=True deviations=['unicode_escape', 'duplicate_keys'] -> next: intensify_near_crash (mutate structurally around the crashing input)
- iter 5: build rejected (strategy does not parse: unterminated string literal (detected at line 1132) (<unknown>, line 1132)) -> rollback

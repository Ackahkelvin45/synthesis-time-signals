# Strategy evolution

- iter 1: build rejected (import: TypeError: 'OneOfStrategy' object is not callable) -> rollback
- iter 2: acc=0.626 novelty=21 cap_mass=0.005 score=71.1 crash=False deviations=['deep_nesting'] -> next: generate_nesting_toward_cap (target depth 700-950)
- iter 3: acc=0.554 novelty=17 cap_mass=0.062 score=68.2 crash=False deviations=['deep_nesting'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)
- iter 4: acc=0.486 novelty=21 cap_mass=0.124 score=73.5 crash=False deviations=['deep_nesting'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)
- iter 5: build rejected (strategy does not parse: unexpected character after line continuation character (<unknown>, line 275)) -> rollback

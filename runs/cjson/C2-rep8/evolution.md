# Strategy evolution

- iter 1: build rejected (strategy does not parse: (unicode error) 'unicodeescape' codec can't decode bytes in position 2-3: truncated \uXXXX escape (<unknown>, line 24)) -> rollback
- iter 2: acc=0.297 novelty=12 cap_mass=0.048 score=48.0 crash=False deviations=['deep_nesting'] -> next: add_or_upweight_production (true)
- iter 3: acc=0.471 novelty=22 cap_mass=0.018 score=72.4 crash=False deviations=['deep_nesting'] -> next: generate_nesting_toward_cap (target depth 700-950)
- iter 4: acc=0.44 novelty=24 cap_mass=0.234 score=78.7 crash=False deviations=['deep_nesting'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)
- iter 5: acc=0.577 novelty=24 cap_mass=0.129 score=76.6 crash=False deviations=['deep_nesting'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)

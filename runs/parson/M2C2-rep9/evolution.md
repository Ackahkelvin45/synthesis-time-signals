# Strategy evolution

- iter 1: acc=0.26 novelty=19 cap_mass=0.055 score=70.1 crash=False deviations=['duplicate_keys'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)
- iter 2: acc=0.271 novelty=14 cap_mass=0.042 score=64.8 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)
- iter 3: acc=0.226 novelty=11 cap_mass=0.291 score=66.8 crash=False deviations=['duplicate_keys'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)
- iter 4: mid-run error (TypeError: integers() got an unexpected keyword argument 'max_size') -> rollback
- iter 5: acc=0.263 novelty=20 cap_mass=0.054 score=71.1 crash=False deviations=['duplicate_keys'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)

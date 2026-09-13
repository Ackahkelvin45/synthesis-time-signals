# Strategy evolution

- iter 1: acc=0.694 novelty=21 cap_mass=0.008 score=71.2 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)
- iter 2: acc=0.654 novelty=22 cap_mass=0.096 score=73.9 crash=False deviations=['duplicate_keys'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)
- iter 3: acc=0.726 novelty=17 cap_mass=0.024 score=67.5 crash=False deviations=['duplicate_keys'] -> next: revert_last_edit (acceptance 0.654->0.726 but novelty 22->17 (quiet failure))
- iter 4: acc=0.72 novelty=28 cap_mass=0.139 score=80.8 crash=False deviations=['duplicate_keys'] -> next: broaden_exploration (coverage saturated; diversify accepted structures)
- iter 5: acc=0.529 novelty=28 cap_mass=0.038 score=78.8 crash=False deviations=['duplicate_keys'] -> next: generate_nesting_toward_cap (target depth 1500-2048)

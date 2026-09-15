# Strategy evolution

- iter 1: acc=0.577 novelty=18 cap_mass=0.0 score=74.4 crash=False deviations=['deep_nesting'] -> next: increase_branch_coverage (branch coverage is 74.4%; reach parser code the current inputs never execute)
- iter 2: acc=0.566 novelty=18 cap_mass=0.0 score=76.1 crash=False deviations=['deep_nesting'] -> next: increase_branch_coverage (branch coverage is 76.1%; reach parser code the current inputs never execute)
- iter 3: gated at acc=0.00; full run skipped
- iter 4: acc=0.583 novelty=17 cap_mass=0.0 score=76.1 crash=False deviations=['deep_nesting'] -> next: increase_branch_coverage (branch coverage is 76.1%; reach parser code the current inputs never execute)
- iter 5: build rejected (strategy does not parse: unexpected character after line continuation character (<unknown>, line 223)) -> rollback

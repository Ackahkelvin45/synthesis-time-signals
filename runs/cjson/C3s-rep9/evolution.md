# Strategy evolution

- iter 1: build rejected (import: NameError: name '_make_array' is not defined) -> rollback
- iter 2: build rejected (strategy does not parse: unterminated string literal (detected at line 14) (<unknown>, line 14)) -> rollback
- iter 3: acc=0.143 novelty=7 cap_mass=0.14 score=77.8 crash=False deviations=['deep_nesting'] -> next: increase_branch_coverage (branch coverage is 77.8%; reach parser code the current inputs never execute)
- iter 4: acc=0.223 novelty=13 cap_mass=0.051 score=80.4 crash=False deviations=['deep_nesting'] -> next: increase_branch_coverage (branch coverage is 80.4%; reach parser code the current inputs never execute)
- iter 5: acc=0.24 novelty=15 cap_mass=0.024 score=80.4 crash=False deviations=['deep_nesting'] -> next: increase_branch_coverage (branch coverage is 80.4%; reach parser code the current inputs never execute)

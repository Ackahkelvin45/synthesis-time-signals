# Strategy evolution

- iter 1: acc=0.38 novelty=16 cap_mass=0.03 score=72.4 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 2: build rejected (strategy does not parse: unterminated string literal (detected at line 235) (<unknown>, line 235)) -> rollback
- iter 3: acc=0.383 novelty=19 cap_mass=0.007 score=73.9 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: acc=0.326 novelty=13 cap_mass=0.018 score=77.3 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 5: acc=0.34 novelty=18 cap_mass=0.008 score=77.6 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

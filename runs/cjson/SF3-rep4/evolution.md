# Strategy evolution

- iter 1: build rejected (import: TypeError: unsupported operand type(s) for +: 'JustStrategy' and 'LazyStrategy') -> rollback
- iter 2: acc=0.306 novelty=9 cap_mass=0.0 score=75.6 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: acc=0.646 novelty=28 cap_mass=0.0 score=76.1 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: acc=0.669 novelty=27 cap_mass=0.0 score=77.3 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 5: acc=0.654 novelty=30 cap_mass=0.0 score=77.6 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

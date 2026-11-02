# Strategy evolution

- iter 1: build rejected (import: TypeError: unsupported operand type(s) for +: 'JustStrategy' and 'LazyStrategy') -> rollback
- iter 2: acc=0.223 novelty=11 cap_mass=0.0 score=77.8 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: acc=0.389 novelty=29 cap_mass=0.0 score=79.5 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: acc=0.429 novelty=25 cap_mass=0.0 score=79.5 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 5: acc=0.357 novelty=24 cap_mass=0.0 score=77.0 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

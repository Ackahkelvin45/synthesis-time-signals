# Strategy evolution

- iter 1: build rejected (import: TypeError: unsupported operand type(s) for +: 'JustStrategy' and 'LazyStrategy') -> rollback
- iter 2: acc=0.437 novelty=15 cap_mass=0.013 score=55.3 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: acc=0.497 novelty=22 cap_mass=0.0 score=72.0 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: acc=0.451 novelty=24 cap_mass=0.025 score=74.5 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 5: acc=0.523 novelty=21 cap_mass=0.022 score=71.4 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

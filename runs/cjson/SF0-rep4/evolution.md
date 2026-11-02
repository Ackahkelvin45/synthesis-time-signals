# Strategy evolution

- iter 1: build rejected (import: TypeError: unsupported operand type(s) for +: 'JustStrategy' and 'LazyStrategy') -> rollback
- iter 2: acc=0.777 novelty=14 cap_mass=0.0 score=64.0 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: acc=0.769 novelty=16 cap_mass=0.0 score=66.0 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: acc=0.743 novelty=12 cap_mass=0.0 score=62.0 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 5: acc=0.78 novelty=13 cap_mass=0.0 score=63.0 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

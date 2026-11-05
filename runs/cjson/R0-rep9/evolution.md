# Strategy evolution

- iter 1: build rejected (import: NameError: name '_array' is not defined) -> rollback
- iter 2: acc=0.56 novelty=22 cap_mass=0.0 score=57.0 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: acc=0.56 novelty=23 cap_mass=0.0 score=58.0 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: acc=0.531 novelty=20 cap_mass=0.0 score=55.0 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 5: acc=0.54 novelty=19 cap_mass=0.0 score=54.0 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

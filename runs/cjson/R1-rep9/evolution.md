# Strategy evolution

- iter 1: build rejected (import: NameError: name '_array' is not defined) -> rollback
- iter 2: acc=0.414 novelty=22 cap_mass=0.0 score=67.0 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: acc=0.351 novelty=22 cap_mass=0.0 score=62.0 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: acc=0.386 novelty=27 cap_mass=0.0 score=77.0 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 5: acc=0.431 novelty=29 cap_mass=0.0 score=79.0 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

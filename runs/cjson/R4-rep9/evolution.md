# Strategy evolution

- iter 1: build rejected (import: NameError: name '_array' is not defined) -> rollback
- iter 2: acc=0.391 novelty=24 cap_mass=0.0 score=74.7 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: acc=0.437 novelty=23 cap_mass=0.0 score=76.4 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: acc=0.351 novelty=18 cap_mass=0.0 score=74.2 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 5: acc=0.437 novelty=17 cap_mass=0.0 score=74.4 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

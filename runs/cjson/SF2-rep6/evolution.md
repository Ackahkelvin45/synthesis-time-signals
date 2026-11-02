# Strategy evolution

- iter 1: acc=0.169 novelty=7 cap_mass=0.0 score=77.3 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 2: acc=0.177 novelty=10 cap_mass=0.016 score=77.3 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: acc=0.18 novelty=11 cap_mass=0.032 score=78.4 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: mid-run error (InvalidArgument: Expected a SearchStrategy but got '' (type=str)) -> rollback
- iter 5: acc=0.169 novelty=13 cap_mass=0.068 score=77.8 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

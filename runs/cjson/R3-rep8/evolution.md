# Strategy evolution

- iter 1: acc=0.651 novelty=28 cap_mass=0.0 score=77.3 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 2: acc=0.777 novelty=30 cap_mass=0.0 score=74.4 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: acc=0.703 novelty=31 cap_mass=0.0 score=74.7 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: mid-run error (ExceptionGroup: Hypothesis found 2 distinct failures. (2 sub-exceptions)) -> rollback
- iter 5: acc=0.789 novelty=28 cap_mass=0.0 score=75.6 crash=False deviations=['deep_nesting'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

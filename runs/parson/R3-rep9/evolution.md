# Strategy evolution

- iter 1: acc=0.394 novelty=12 cap_mass=0.688 score=73.9 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 2: acc=0.423 novelty=19 cap_mass=0.439 score=74.5 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: acc=0.586 novelty=32 cap_mass=0.307 score=75.8 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: mid-run error (ExceptionGroup: Hypothesis found 2 distinct failures. (2 sub-exceptions)) -> rollback
- iter 5: acc=0.58 novelty=27 cap_mass=0.266 score=76.1 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

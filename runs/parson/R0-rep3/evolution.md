# Strategy evolution

- iter 1: acc=0.386 novelty=35 cap_mass=0.126 score=87.5 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 2: acc=0.463 novelty=40 cap_mass=0.259 score=95.2 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: acc=0.494 novelty=39 cap_mass=0.295 score=94.9 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: acc=0.297 novelty=31 cap_mass=0.077 score=82.5 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 5: mid-run error (IndexError: string index out of range) -> rollback

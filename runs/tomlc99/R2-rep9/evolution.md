# Strategy evolution

- iter 1: acc=0.697 novelty=42 cap_mass=0.17 score=61.1 crash=False deviations=[] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 2: acc=0.61 novelty=75 cap_mass=0.292 score=71.3 crash=False deviations=[] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: acc=0.656 novelty=78 cap_mass=0.083 score=73.5 crash=False deviations=[] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: mid-run error (AttributeError: 'SampledFromStrategy' object has no attribute 'join') -> rollback
- iter 5: acc=0.505 novelty=28 cap_mass=0.02 score=63.1 crash=False deviations=[] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

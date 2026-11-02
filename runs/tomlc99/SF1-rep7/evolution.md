# Strategy evolution

- iter 1: build rejected (import: NameError: name '_key' is not defined) -> rollback
- iter 2: acc=0.481 novelty=34 cap_mass=0.042 score=229.8 crash=False deviations=[] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: acc=0.43 novelty=45 cap_mass=0.061 score=231.2 crash=False deviations=[] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: build rejected (import: TypeError: 'LazyStrategy' object is not callable) -> rollback
- iter 5: acc=0.451 novelty=42 cap_mass=0.057 score=228.1 crash=False deviations=[] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

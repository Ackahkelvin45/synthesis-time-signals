# Strategy evolution

- iter 1: build rejected (import: NameError: name '_make_obj' is not defined) -> rollback
- iter 2: acc=0.554 novelty=25 cap_mass=0.103 score=74.2 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: acc=0.531 novelty=25 cap_mass=0.118 score=72.3 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: acc=0.629 novelty=25 cap_mass=0.164 score=68.8 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 5: acc=0.637 novelty=18 cap_mass=0.135 score=72.3 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

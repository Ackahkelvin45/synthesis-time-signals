# Strategy evolution

- iter 1: build rejected (import: NameError: name '_make_obj' is not defined) -> rollback
- iter 2: acc=0.48 novelty=17 cap_mass=0.006 score=67.1 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: acc=0.497 novelty=14 cap_mass=0.109 score=66.2 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: acc=0.469 novelty=15 cap_mass=0.165 score=68.3 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 5: acc=0.606 novelty=21 cap_mass=0.156 score=74.1 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

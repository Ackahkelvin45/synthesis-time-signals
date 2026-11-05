# Strategy evolution

- iter 1: build rejected (import: NameError: name '_make_obj' is not defined) -> rollback
- iter 2: acc=0.346 novelty=12 cap_mass=0.0 score=73.4 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: acc=0.317 novelty=8 cap_mass=0.0 score=76.1 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: acc=0.837 novelty=39 cap_mass=0.0 score=71.7 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 5: acc=0.914 novelty=45 cap_mass=0.0 score=70.4 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

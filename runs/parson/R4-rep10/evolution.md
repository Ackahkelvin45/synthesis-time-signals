# Strategy evolution

- iter 1: build rejected (import: NameError: name '_make_obj' is not defined) -> rollback
- iter 2: gated at acc=0.00; full run skipped
- iter 3: acc=0.52 novelty=26 cap_mass=0.154 score=72.3 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: acc=0.569 novelty=25 cap_mass=0.04 score=73.6 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 5: acc=0.589 novelty=30 cap_mass=0.039 score=73.9 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

# Strategy evolution

- iter 1: build rejected (import: NameError: name '_key' is not defined) -> rollback
- iter 2: acc=0.563 novelty=54 cap_mass=0.416 score=70.7 crash=False deviations=[] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: acc=0.771 novelty=46 cap_mass=0.204 score=68.0 crash=False deviations=[] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 4: acc=0.651 novelty=20 cap_mass=0.057 score=62.2 crash=False deviations=[] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 5: build rejected (strategy does not parse: invalid syntax (<unknown>, line 1)) -> rollback

# Strategy evolution

- iter 1: build rejected (import: NameError: name '_array_of' is not defined) -> rollback
- iter 2: build rejected (import: NameError: name '_array' is not defined) -> rollback
- iter 3: build rejected (strategy does not parse: invalid syntax (<unknown>, line 1)) -> rollback
- iter 4: acc=0.651 novelty=64 cap_mass=0.145 score=281.9 crash=False deviations=[] -> next: add_or_upweight_production (NAN)
- iter 5: acc=0.646 novelty=63 cap_mass=0.062 score=274.2 crash=False deviations=[] -> next: add_or_upweight_production (OFFSET_DATE_TIME)

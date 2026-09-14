# Strategy evolution

- iter 1: build rejected (strategy does not parse: unterminated string literal (detected at line 855) (<unknown>, line 855)) -> rollback
- iter 2: acc=0.443 novelty=62 cap_mass=0.368 score=259.4 crash=False deviations=[] -> next: add_or_upweight_production (bool_)
- iter 3: acc=0.483 novelty=75 cap_mass=0.284 score=285.7 crash=False deviations=[] -> next: add_or_upweight_production (NAN)
- iter 4: acc=0.529 novelty=71 cap_mass=0.389 score=278.8 crash=False deviations=[] -> next: add_or_upweight_production (ML_BASIC_STRING)
- iter 5: acc=0.443 novelty=68 cap_mass=0.406 score=256.1 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 256.1 < best 285.7)

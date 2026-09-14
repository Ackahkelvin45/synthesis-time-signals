# Strategy evolution

- iter 1: acc=0.403 novelty=46 cap_mass=0.355 score=72.2 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)
- iter 2: acc=0.589 novelty=45 cap_mass=0.117 score=58.9 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 58.9 < best 72.2)
- iter 3: acc=0.374 novelty=51 cap_mass=0.267 score=72.5 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)
- iter 4: acc=0.526 novelty=28 cap_mass=0.049 score=53.5 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 53.5 < best 72.5)
- iter 5: acc=0.357 novelty=52 cap_mass=0.32 score=69.1 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)

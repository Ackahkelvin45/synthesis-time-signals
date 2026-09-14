# Strategy evolution

- iter 1: acc=0.569 novelty=66 cap_mass=0.131 score=70.2 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)
- iter 2: acc=0.589 novelty=41 cap_mass=0.068 score=62.2 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 62.2 < best 70.2)
- iter 3: acc=0.48 novelty=55 cap_mass=0.149 score=74.8 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)
- iter 4: acc=0.594 novelty=40 cap_mass=0.058 score=70.1 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)
- iter 5: acc=0.54 novelty=35 cap_mass=0.058 score=59.4 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 59.4 < best 74.8)

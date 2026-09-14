# Strategy evolution

- iter 1: acc=0.08 novelty=18 cap_mass=0.0 score=60.5 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)
- iter 2: acc=0.251 novelty=17 cap_mass=0.0 score=55.7 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)
- iter 3: acc=0.364 novelty=12 cap_mass=0.0 score=42.4 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 42.4 < best 60.5)
- iter 4: acc=0.103 novelty=19 cap_mass=0.0 score=61.9 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)
- iter 5: acc=0.277 novelty=11 cap_mass=0.0 score=48.1 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 48.1 < best 61.9)

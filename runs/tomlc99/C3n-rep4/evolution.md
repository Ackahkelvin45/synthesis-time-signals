# Strategy evolution

- iter 1: acc=0.417 novelty=38 cap_mass=0.486 score=63.8 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)
- iter 2: acc=0.817 novelty=31 cap_mass=0.122 score=58.8 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)
- iter 3: acc=0.874 novelty=32 cap_mass=0.039 score=56.2 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 56.2 < best 63.8)
- iter 4: acc=0.543 novelty=39 cap_mass=0.542 score=70.0 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)
- iter 5: acc=0.54 novelty=37 cap_mass=0.243 score=62.4 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 62.4 < best 70.0)

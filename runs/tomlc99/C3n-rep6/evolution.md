# Strategy evolution

- iter 1: acc=0.611 novelty=54 cap_mass=0.43 score=69.5 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)
- iter 2: acc=0.786 novelty=26 cap_mass=0.044 score=58.8 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 58.8 < best 69.5)
- iter 3: acc=0.649 novelty=66 cap_mass=0.3 score=71.7 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)
- iter 4: acc=0.709 novelty=24 cap_mass=0.069 score=58.5 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 58.5 < best 71.7)
- iter 5: acc=0.617 novelty=58 cap_mass=0.412 score=72.9 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)

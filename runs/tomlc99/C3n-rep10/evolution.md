# Strategy evolution

- iter 1: mid-run error (RecursionError: maximum recursion depth exceeded) -> rollback
- iter 2: acc=0.129 novelty=27 cap_mass=0.111 score=72.2 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)
- iter 3: acc=0.3 novelty=28 cap_mass=0.038 score=65.7 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)
- iter 4: acc=0.335 novelty=22 cap_mass=0.094 score=62.9 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 62.9 < best 72.2)
- iter 5: acc=0.089 novelty=20 cap_mass=0.097 score=73.4 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)

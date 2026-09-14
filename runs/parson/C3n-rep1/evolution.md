# Strategy evolution

- iter 1: build rejected (strategy does not parse: unterminated string literal (detected at line 16) (<unknown>, line 16)) -> rollback
- iter 2: acc=0.551 novelty=26 cap_mass=0.254 score=70.4 crash=False deviations=['duplicate_keys'] -> next: cover_function (json_serialize_string has 0% branch coverage; generate inputs that exercise it)
- iter 3: acc=0.72 novelty=20 cap_mass=0.103 score=70.9 crash=False deviations=['duplicate_keys'] -> next: cover_function (json_serialize_string has 0% branch coverage; generate inputs that exercise it)
- iter 4: acc=0.777 novelty=14 cap_mass=0.07 score=66.6 crash=False deviations=['duplicate_keys'] -> next: cover_function (json_serialize_string has 0% branch coverage; generate inputs that exercise it)
- iter 5: acc=0.623 novelty=15 cap_mass=0.064 score=69.3 crash=False deviations=['duplicate_keys'] -> next: cover_function (json_serialize_string has 0% branch coverage; generate inputs that exercise it)

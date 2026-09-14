# Strategy evolution

- iter 1: build rejected (import: InvalidArgument: Did you mean st.sampled_from([<function _array_of.<locals>.build at 0x10a8bd1c0>, <function _inline_table_of.<locals>.build at 0x10a8bd260>])?  st.one_of() is used to combine ) -> rollback
- iter 2: acc=0.363 novelty=28 cap_mass=0.0 score=54.2 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)
- iter 3: acc=0.297 novelty=13 cap_mass=0.0 score=42.4 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 42.4 < best 54.2)
- iter 4: acc=0.446 novelty=28 cap_mass=0.019 score=51.4 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)
- iter 5: acc=0.457 novelty=33 cap_mass=0.044 score=54.4 crash=False deviations=[] -> next: cover_function (toml_utf8_to_ucs has 0% branch coverage; generate inputs that exercise it)

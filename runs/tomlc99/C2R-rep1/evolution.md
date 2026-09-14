# Strategy evolution

- iter 1: acc=0.169 novelty=26 cap_mass=0.153 score=199.1 crash=False deviations=[] -> next: add_or_upweight_production (bool_)
- iter 2: acc=0.303 novelty=35 cap_mass=0.038 score=200.8 crash=False deviations=[] -> next: add_or_upweight_production (inline_table_keyvals_non_empty)
- iter 3: acc=0.166 novelty=29 cap_mass=0.138 score=226.8 crash=False deviations=[] -> next: add_or_upweight_production (ML_LITERAL_STRING)
- iter 4: acc=0.154 novelty=28 cap_mass=0.056 score=189.1 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 189.1 < best 226.8)
- iter 5: acc=0.114 novelty=23 cap_mass=0.15 score=166.0 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 166.0 < best 226.8)

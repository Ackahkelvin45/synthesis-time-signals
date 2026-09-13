# Strategy evolution

- iter 1: acc=0.203 novelty=37 cap_mass=0.07 score=243.4 crash=False deviations=[] -> next: add_or_upweight_production (bool_)
- iter 2: acc=0.206 novelty=40 cap_mass=0.028 score=255.6 crash=False deviations=[] -> next: add_or_upweight_production (LOCAL_DATE_TIME)
- iter 3: acc=0.229 novelty=41 cap_mass=0.163 score=264.3 crash=False deviations=[] -> next: fix_feature_encoding (duplicate_keys probe accepted only 0%)
- iter 4: acc=0.169 novelty=35 cap_mass=0.0 score=225.0 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 225.0 < best 264.3)
- iter 5: acc=0.18 novelty=38 cap_mass=0.079 score=259.6 crash=False deviations=[] -> next: fix_feature_encoding (duplicate_keys probe accepted only 0%)

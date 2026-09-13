# Strategy evolution

- iter 1: build rejected (import: InvalidArgument: Did you mean st.sampled_from([<function _complete_doc at 0x10b175080>, <function _edge_document at 0x10b174e00>, <function _deep_array at 0x10b174ea0>, <function _deep_inline ) -> rollback
- iter 2: acc=0.494 novelty=68 cap_mass=0.0 score=263.0 crash=False deviations=[] -> next: add_or_upweight_production (bool_)
- iter 3: acc=0.514 novelty=78 cap_mass=0.0 score=288.0 crash=False deviations=[] -> next: add_or_upweight_production (ML_LITERAL_STRING)
- iter 4: acc=0.694 novelty=62 cap_mass=0.0 score=257.0 crash=False deviations=[] REGRESSION->rollback next: revert_last_edit (score 257.0 < best 288.0)
- iter 5: acc=0.489 novelty=70 cap_mass=0.0 score=280.0 crash=False deviations=[] -> next: add_or_upweight_production (NAN)

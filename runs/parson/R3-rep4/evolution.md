# Strategy evolution

- iter 1: acc=0.371 novelty=28 cap_mass=0.177 score=72.5 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 2: acc=0.32 novelty=22 cap_mass=0.098 score=71.5 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 3: mid-run error (HypothesisException: Using example() inside a strategy definition is a bad idea. Instead consider using hypothesis.strategies.builds() or @hypothesis.strategies.composite to define your strategy. See ) -> rollback
- iter 4: acc=0.286 novelty=20 cap_mass=0.15 score=72.3 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)
- iter 5: acc=0.271 novelty=25 cap_mass=0.179 score=71.7 crash=False deviations=['duplicate_keys'] -> next: improve_strategy (make it a better fuzzer for this grammar, using the run feedback above where it is given)

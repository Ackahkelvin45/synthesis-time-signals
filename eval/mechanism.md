# Mechanism: how the proxy loop collapses (log-only analysis)

Replicates: C2 30 (4 collapsed), A5 30 (0 collapsed). Sources: iter-N/prompt.md (the edit instruction the model received), iter-N/stats.json (gate), strategy.py (code), evolution.md. No runs, no API calls.

## T1. Fixation: do collapsed replicates repeat the same edit and the same code?

| group | n | distinct edit instructions (of 4 refinements) | consecutive identical edits | mean code similarity between consecutive iterations |
|---|---|---|---|---|
| C2 collapsed | 4 | 1.00 | 3.00 | 0.984 |
| C2 healthy | 26 | 2.46 | 1.27 | 0.878 |
| A5 (contrast) | 30 | 1.20 | 2.80 | 0.927 |

Per collapsed replicate (edit instruction per iteration; code similarity to the previous iteration):

- **json-parser C2-rep7**: gates ['gated', 'gated', 'gated', 'gated', 'gated']
  - iter 1: SEED: initial seed from grammar
  - iter 2: fix_generator_error: ExceptionGroup: Hypothesis found 2 distinct failures. (2 sub  (code sim 0.752)
  - iter 3: fix_generator_error: ExceptionGroup: Hypothesis found 2 distinct failures. (2 sub  (code sim 1.0)
  - iter 4: fix_generator_error: ExceptionGroup: Hypothesis found 2 distinct failures. (2 sub  (code sim 1.0)
  - iter 5: fix_generator_error: ExceptionGroup: Hypothesis found 2 distinct failures. (2 sub  (code sim 1.0)
- **json-parser C2-rep10**: gates ['gated', 'gated', 'gated', 'gated', 'gated']
  - iter 1: SEED: initial seed from grammar
  - iter 2: fix_generator_error: ExceptionGroup: Hypothesis found 2 distinct failures. (2 sub  (code sim 1.0)
  - iter 3: fix_generator_error: ExceptionGroup: Hypothesis found 2 distinct failures. (2 sub  (code sim 1.0)
  - iter 4: fix_generator_error: ExceptionGroup: Hypothesis found 2 distinct failures. (2 sub  (code sim 1.0)
  - iter 5: fix_generator_error: ExceptionGroup: Hypothesis found 2 distinct failures. (2 sub  (code sim 1.0)
- **parson C2-rep6**: gates ['gated', 'gated', 'gated', 'gated', 'gated']
  - iter 1: SEED: initial seed from grammar
  - iter 2: fix_generator_error: TypeError: can only concatenate str (not "OneOfStrategy") to  (code sim 0.999)
  - iter 3: fix_generator_error: TypeError: can only concatenate str (not "OneOfStrategy") to  (code sim 0.992)
  - iter 4: fix_generator_error: TypeError: can only concatenate str (not "OneOfStrategy") to  (code sim 1.0)
  - iter 5: fix_generator_error: TypeError: can only concatenate str (not "OneOfStrategy") to  (code sim 1.0)
- **tomlc99 C2-rep3**: gates ['gated', 'gated', 'gated', 'gated', 'gated']
  - iter 1: SEED: initial seed from grammar
  - iter 2: fix_generator_error: AttributeError: 'function' object has no attribute 'validate  (code sim 1.0)
  - iter 3: fix_generator_error: AttributeError: 'function' object has no attribute 'validate  (code sim 1.0)
  - iter 4: fix_generator_error: AttributeError: 'function' object has no attribute 'validate  (code sim 1.0)
  - iter 5: fix_generator_error: AttributeError: 'function' object has no attribute 'validate  (code sim 1.0)

Edit instructions across healthy C2 replicates (iterations 2-5): intensify_near_crash 31, add_or_upweight_production 21, broaden_exploration 16, revert_last_edit 13, generate_nesting_toward_cap 12, fix_generator_error 5, RESEED 5, fix_feature_encoding 1

## T2. Do gate events predict collapse within the C2 arm?

Iteration-1 gated: collapsed 4/4, healthy 5/26; Fisher exact two-sided p = 0.0046.
Gate events per replicate: collapsed [5, 5, 5, 5] (by definition 5); healthy [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 1, 2, 3, 1, 0, 1, 0] (mean 0.46). Note: 'collapsed' is defined as five gated iterations, so total gate count is tautological; the informative test is the iteration-1 gate above, and the recovery question below.

Healthy C2 replicates whose iteration 1 was gated but that recovered: 5 (tomlc99 rep2, tomlc99 rep5, tomlc99 rep6, tomlc99 rep7, tomlc99 rep9).
A5 replicates with any gate event: 7/30; iteration-1 gated: 4/30; collapsed: 0.

## Cross-arm collapse rate

C2 4/30 vs A5 0/30; Fisher exact two-sided p = 0.1124.

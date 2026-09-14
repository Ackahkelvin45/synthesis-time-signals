# RQ5: author-failure taxonomy (log-only, exploratory)

Guard events over 141 completed replicates (arms C2, A5, C3s, C3n, C2R; targets json-parser, parson, tomlc99, cjson), coded from recorded exception and rejection text by ordered regexes (first match wins). 101 events. Iterations with no event are not listed.

## Cause class by arm (events)

| cause | C2 | A5 | C3s | C3n | C2R | total |
|---|---|---|---|---|---|---|
| strategy/value confusion (two-level semantics) | 11 | 1 | 6 | 2 | 0 | 20 |
| syntax / unparseable response | 3 | 2 | 6 | 5 | 1 | 17 |
| generic Python error (TypeError/ValueError/KeyError/NameError) | 3 | 3 | 2 | 2 | 4 | 14 |
| ExceptionGroup wrapper (sub-exceptions hidden) | 13 | 0 | 0 | 0 | 0 | 13 |
| recursion / Hypothesis health check | 1 | 0 | 10 | 1 | 0 | 12 |
| hallucinated Hypothesis API | 5 | 0 | 3 | 0 | 1 | 9 |
| low acceptance (valid code, invalid outputs) | 0 | 5 | 0 | 0 | 1 | 6 |
| wrong alphabet / characters argument | 0 | 0 | 4 | 0 | 1 | 5 |
| invalid strategy arguments | 1 | 0 | 1 | 1 | 0 | 3 |
| disallowed import or name (screen) | 0 | 0 | 1 | 0 | 1 | 2 |

## Event kind by target

| kind | json-parser | parson | tomlc99 | cjson |
|---|---|---|---|
| build rejection | 17 | 2 | 22 | 0 |
| gate failure | 25 | 6 | 19 | 5 |
| mid-run error | 0 | 0 | 5 | 0 |

## Replicates with at least one event, by arm and target

| arm | json-parser | parson | tomlc99 | cjson |
|---|---|---|---|
| C2 | 3/10 | 1/10 | 7/10 | 1/1 |
| A5 | 4/10 | 0/10 | 3/10 | - |
| C3s | 5/10 | 2/10 | 7/10 | - |
| C3n | 3/10 | 1/10 | 5/10 | - |
| C2R | 3/10 | - | 3/10 | - |

Iteration-1 (seed) failures: 34 events in 34 replicates; by class: generic Python error (TypeError/ValueError/KeyError/NameError) 8, recursion / Hypothesis health check 6, strategy/value confusion (two-level semantics) 6, syntax / unparseable response 4, ExceptionGroup wrapper (sub-exceptions hidden) 3, invalid strategy arguments 2, wrong alphabet / characters argument 2, disallowed import or name (screen) 2, hallucinated Hypothesis API 1

## Unclassified (0), verbatim for audit


## One example per class

- **syntax / unparseable response**: json-parser C2-rep3 iter 3: `build rejected (strategy does not parse: unterminated string literal (detected at line 557) (<unknown>, line 557)) -> rollback`
- **ExceptionGroup wrapper (sub-exceptions hidden)**: json-parser C2-rep7 iter 1: `ExceptionGroup: Hypothesis found 2 distinct failures. (2 sub-exceptions)`
- **generic Python error (TypeError/ValueError/KeyError/NameError)**: json-parser A5-rep2 iter 1: `build rejected (import: NameError: name '_array' is not defined) -> rollback`
- **low acceptance (valid code, invalid outputs)**: json-parser A5-rep7 iter 4: `acceptance 0.041666666666666664`
- **recursion / Hypothesis health check**: json-parser C3s-rep9 iter 1: `RecursionError: maximum recursion depth exceeded`
- **strategy/value confusion (two-level semantics)**: json-parser C3s-rep9 iter 3: `InvalidArgument: Expected a SearchStrategy but got None (type=NoneType)`
- **hallucinated Hypothesis API**: json-parser C2R-rep10 iter 2: `build rejected (import: AttributeError: 'function' object has no attribute 'calc_is_cacheable') -> rollback`
- **invalid strategy arguments**: tomlc99 C2-rep7 iter 1: `build rejected (import: InvalidArgument: Did you mean st.sampled_from([<function _complete_doc at 0x10b175080>, <function _edge_document at `
- **wrong alphabet / characters argument**: tomlc99 C3s-rep8 iter 1: `InvalidArgument: The following elements in alphabet are not of length one, which leads to violation of size constraints:  ['\\"', '\\\\', '\`
- **disallowed import or name (screen)**: tomlc99 C3s-rep10 iter 1: `build rejected (dunder attribute access: __class__) -> rollback`

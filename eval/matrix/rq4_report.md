# RQ4: ground-truth bug campaigns (exploratory)

173 campaigns; budget [30.0] minutes each; a campaign counts as triggered when an input's normalised crash signature matches the bug's proof of concept (Magma-style). Generators: each registered arm's final per replicate (seed = 1000 x replicate), plus fixed references at seed 0. A final that cannot draw is censored at zero inputs.

## cjson / cve-2023-53154

positive control passed: True; build: pre-fix build bug-cve-2023-53154; campaigns recorded as error (final generator could not draw, censored at 0): 0

| generator | campaigns | triggered | median inputs to trigger | median seconds | inputs run (median) |
|---|---|---|---|---|---|
| Grammarinator defaults (C0b) | 1 | 0 | - | - | 10000000 |
| Grammarinator depth-matched (C0b) | 1 | 0 | - | - | 10000000 |
| random text (C0a) | 1 | 0 | - | - | 7258000 |


## json-parser / issue68 (this pre-fix build also contains issue 78, which shares the signature: the row measures either end-of-buffer over-read)

positive control passed: True; build: pre-fix build bug-issue68; campaigns recorded as error (final generator could not draw, censored at 0): 5

| generator | campaigns | triggered | median inputs to trigger | median seconds | inputs run (median) |
|---|---|---|---|---|---|
| C2 | 10 | 4 | 1015.0 | 24.765 | 27000 |
| A5 | 10 | 9 | 513 | 14.94 | 3000 |
| C3s | 10 | 5 | 1550 | 28.75 | 6000 |
| C3n | 10 | 6 | 3230.5 | 19.740000000000002 | 9000 |
| Grammarinator defaults (C0b) | 1 | 0 | - | - | 5620000 |
| Grammarinator depth-matched (C0b) | 1 | 0 | - | - | 10000000 |
| random text (C0a) | 1 | 0 | - | - | 3020000 |

- C2 4/10 vs A5 9/10 triggered: Fisher exact p = 0.057
- C3s 5/10 vs C2 4/10 triggered: Fisher exact p = 1.000
- C3n 6/10 vs C2 4/10 triggered: Fisher exact p = 0.656

## json-parser / issue78

positive control passed: True; build: pre-fix build bug-issue78; campaigns recorded as error (final generator could not draw, censored at 0): 5

| generator | campaigns | triggered | median inputs to trigger | median seconds | inputs run (median) |
|---|---|---|---|---|---|
| C2 | 10 | 3 | 1379 | 3.29 | 182000 |
| A5 | 10 | 9 | 2051 | 1.76 | 4000 |
| C3s | 10 | 5 | 1550 | 4.23 | 8000 |
| C3n | 10 | 5 | 5286 | 2.78 | 49000 |
| Grammarinator defaults (C0b) | 1 | 0 | - | - | 10000000 |
| Grammarinator depth-matched (C0b) | 1 | 0 | - | - | 6320000 |
| random text (C0a) | 1 | 0 | - | - | 3032000 |

- C2 3/10 vs A5 9/10 triggered: Fisher exact p = 0.020
- C3s 5/10 vs C2 3/10 triggered: Fisher exact p = 0.650
- C3n 5/10 vs C2 3/10 triggered: Fisher exact p = 0.650

## tomlc99 / issue50

positive control passed: True; build: pre-fix build bug-issue50; campaigns recorded as error (final generator could not draw, censored at 0): 2

| generator | campaigns | triggered | median inputs to trigger | median seconds | inputs run (median) |
|---|---|---|---|---|---|
| C2 | 10 | 8 | 6361.0 | 52.065000000000005 | 7000 |
| A5 | 10 | 9 | 3693 | 73.99 | 8000 |
| C3s | 10 | 9 | 13057 | 71.39 | 10000 |
| C3n | 10 | 9 | 44680 | 141.59 | 54000 |
| Grammarinator defaults (C0b) | 1 | 1 | 10969 | 47.62 | 12000 |
| random text (C0a) | 1 | 0 | - | - | 6194000 |

- C2 8/10 vs A5 9/10 triggered: Fisher exact p = 1.000
- C3s 9/10 vs C2 8/10 triggered: Fisher exact p = 1.000
- C3n 9/10 vs C2 8/10 triggered: Fisher exact p = 1.000

## tomlc99 / recursion

positive control passed: True; build: pinned HEAD (bug unfixed upstream); campaigns recorded as error (final generator could not draw, censored at 0): 3

| generator | campaigns | triggered | median inputs to trigger | median seconds | inputs run (median) |
|---|---|---|---|---|---|
| C2 | 10 | 0 | - | - | 423000 |
| A5 | 10 | 0 | - | - | 419000 |
| C3s | 10 | 0 | - | - | 651000 |
| C3n | 10 | 0 | - | - | 898000 |
| Grammarinator defaults (C0b) | 1 | 0 | - | - | 4084000 |
| random text (C0a) | 1 | 0 | - | - | 6208000 |

- C2 0/10 vs A5 0/10 triggered: Fisher exact p = 1.000
- C3s 0/10 vs C2 0/10 triggered: Fisher exact p = 1.000
- C3n 0/10 vs C2 0/10 triggered: Fisher exact p = 1.000

## Other crash signatures seen during campaigns (candidate findings, by target)

- json-parser: `ubsan:signed-integer-overflow|json_parse_ex>harness_parse>run_batch_mode` x31129
- tomlc99: `asan:heap-buffer-overflow|scan_string>next_token>parse_keyval` x21261
- tomlc99: `asan:heap-buffer-overflow|scan_string>next_token>toml_parse` x4741
- tomlc99: `timeout` x2269
- json-parser: `timeout` x1081
- tomlc99: `asan:heap-buffer-overflow|scan_string>next_token>eat_token` x1024
- tomlc99: `asan:heap-buffer-overflow|toml_rtoi>valtype>parse_array` x39

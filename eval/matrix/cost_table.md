# T6: synthesis cost per run (mean over replicates; every completed run)

| target | arm | runs | LLM calls | tokens in | tokens out | USD | wall min | CPU s | served |
|---|---|---|---|---|---|---|---|---|---|
| json-parser | C2 | 10 | 6.4 | 21347 | 22503 | 0.031 | 6.5 | 155 | deepseek-flash |
| json-parser | A5 | 10 | 5.6 | 14898 | 15446 | 0.021 | 9.4 | 220 | deepseek-flash |
| json-parser | C3s | 10 | 6.2 | 19158 | 20572 | 0.028 | 3.2 | 63 | deepseek-flash |
| json-parser | C3n | 10 | 5.1 | 15696 | 17113 | 0.023 | 3.7 | 88 | deepseek-flash |
| json-parser | C2R | 10 | 5.4 | 16156 | 17246 | 0.023 | 4.9 | 111 | deepseek-flash |
| parson | C2 | 10 | 5.6 | 15811 | 15586 | 0.021 | 3.8 | 165 | deepseek-flash |
| parson | A5 | 10 | 5.2 | 14174 | 14163 | 0.019 | 4.1 | 184 | deepseek-flash |
| parson | C3s | 10 | 5.3 | 17145 | 19670 | 0.026 | 4.2 | 146 | deepseek-flash |
| parson | C3n | 10 | 5.0 | 14854 | 16132 | 0.022 | 3.7 | 158 | deepseek-flash |
| parson | M2C2 | 10 | 5.4 | 13917 | 20166 | 0.044 | 5.6 | 157 | gpt-5-mini-2025-08-07 |
| parson | M2A5 | 10 | 5.1 | 12121 | 20555 | 0.044 | 5.5 | 150 | gpt-5-mini-2025-08-07 |
| parson | M2C3s | 10 | 5.2 | 12759 | 20455 | 0.044 | 5.7 | 162 | gpt-5-mini-2025-08-07 |
| tomlc99 | C2 | 10 | 5.6 | 24579 | 23166 | 0.032 | 4.0 | 160 | deepseek-flash |
| tomlc99 | A5 | 10 | 5.2 | 21670 | 22097 | 0.030 | 4.3 | 174 | deepseek-flash |
| tomlc99 | C3s | 10 | 6.4 | 29060 | 30540 | 0.041 | 3.6 | 108 | deepseek-flash |
| tomlc99 | C3n | 10 | 5.3 | 23036 | 23978 | 0.033 | 4.0 | 147 | deepseek-flash |
| tomlc99 | C2R | 10 | 5.3 | 22553 | 20732 | 0.029 | 3.7 | 135 | deepseek-flash |
| tomlc99 | M2C2 | 10 | 6.2 | 25745 | 33689 | 0.074 | 10.2 | 139 | gpt-5-mini-2025-08-07 |
| tomlc99 | M2A5 | 10 | 5.8 | 22470 | 35205 | 0.076 | 14.1 | 227 | gpt-5-mini-2025-08-07 |
| tomlc99 | M2C3s | 10 | 5.4 | 20377 | 30647 | 0.066 | 11.2 | 177 | gpt-5-mini-2025-08-07 |
| cjson | C2 | 10 | 5.6 | 14079 | 14176 | 0.019 | 3.8 | 168 | deepseek-flash |
| cjson | A5 | 10 | 5.2 | 12285 | 13106 | 0.018 | 4.5 | 207 | deepseek-flash |
| cjson | C3s | 10 | 5.9 | 15375 | 17311 | 0.023 | 3.7 | 152 | deepseek-flash |
| cjson | C3n | 10 | 5.4 | 15959 | 17181 | 0.023 | 4.6 | 207 | deepseek-flash |

All runs: 240; total 8.116 USD; mean 0.034 USD, 5.5 min per run; backstop hits 0; served ['deepseek-flash', 'gpt-5-mini-2025-08-07'].
Prices: .env estimates (0.27 USD/M input, 1.10 USD/M output); provider list prices for the served model bracket these (D26 addendum).

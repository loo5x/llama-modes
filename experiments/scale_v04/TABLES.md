# SCALE v0.4 representation experiment

These are descriptive results on synthetic tasks, not evidence of calibration.

## GPT-OSS-20B-MXFP4

Completed 399 matrix rows; 399 successful; 0 errors.

SUM comparisons use total variation distance (TV), from 0 to 1, after aligning by numeric value. The interval mean shift is reported only for interval cases.

| Comparison | Pairs | Mode changes | Median changes | Mean TV | Max TV | Max absolute interval mean shift |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| numeric:sum -> fixed:sum | 39 | 2 | 2 | 0.065465 | 0.614245 | 0.986429 |
| numeric:sum -> symbol:sum | 39 | 3 | 4 | 0.134371 | 0.935530 | 0.875411 |
| numeric:sum -> anchor:sum | 39 | 3 | 4 | 0.123225 | 0.915115 | 1.206359 |
| numeric:sum -> numeric_ended:sum | 39 | 6 | 5 | 0.126302 | 0.693849 | 4.487995 |
| numeric:sum -> numeric_space:sum | 39 | 0 | 1 | 0.049956 | 0.303076 | 0.543521 |
| numeric:sum -> numeric_api_reverse:sum | 39 | 0 | 0 | 0.000032 | 0.001244 | 0.001951 |
| symbol:sum -> symbol_rotate:sum | 39 | 8 | 10 | 0.188126 | 0.863901 | 0.951785 |
| symbol:sum -> symbol_list_reverse:sum | 39 | 6 | 6 | 0.153050 | 0.820610 | 0.940916 |
| numeric:sum -> numeric_raw:sum | 39 | 0 | 0 | 0.000000 | 0.000000 | 0.000000 |
| numeric:sum -> numeric_fine:sum | 9 | 0 | 4 | 0.239185 | 0.425550 | 0.775253 |

SUM versus MEAN on the same scored rows:

| Representation | Cases | Mode changes | Median changes | Mean TV | Max TV |
| --- | ---: | ---: | ---: | ---: | ---: |
| numeric | 39 | 0 | 0 | 0.018903 | 0.197573 |
| fixed | 39 | 0 | 0 | 0.019495 | 0.185087 |
| symbol | 39 | 0 | 0 | 0.000000 | 0.000000 |
| anchor | 39 | 0 | 0 | 0.000000 | 0.000000 |
| numeric_ended | 39 | 6 | 12 | 0.310504 | 0.707957 |
| numeric_space | 39 | 0 | 4 | 0.210394 | 0.404843 |
| numeric_api_reverse | 39 | 0 | 0 | 0.018906 | 0.197711 |
| symbol_rotate | 39 | 0 | 0 | 0.000000 | 0.000000 |
| symbol_list_reverse | 39 | 0 | 0 | 0.000000 | 0.000000 |
| numeric_raw | 39 | 0 | 0 | 0.018903 | 0.197573 |
| numeric_fine | 9 | 3 | 2 | 0.383159 | 0.472717 |

Tokenization of the five main encodings:

| Scale | Encoding | Token counts in value order | Strict-prefix pairs |
| --- | --- | --- | --- |
| 0_10 | numeric | [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1] | [] |
| 0_10 | fixed | [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1] | [] |
| 0_10 | symbol | [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1] | [] |
| 0_10 | anchor | [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1] | [] |
| 0_10 | numeric_ended | [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2] | [] |
| 1_5 | numeric | [1, 1, 1, 1, 1] | [] |
| 1_5 | fixed | [1, 1, 1, 1, 1] | [] |
| 1_5 | symbol | [1, 1, 1, 1, 1] | [] |
| 1_5 | anchor | [1, 1, 1, 1, 1] | [] |
| 1_5 | numeric_ended | [2, 2, 2, 2, 2] | [] |
| minus2_2 | numeric | [2, 2, 1, 1, 1] | [] |
| minus2_2 | fixed | [2, 2, 2, 2, 2] | [] |
| minus2_2 | symbol | [1, 1, 1, 1, 1] | [] |
| minus2_2 | anchor | [1, 1, 1, 1, 1] | [] |
| minus2_2 | numeric_ended | [3, 3, 2, 2, 2] | [] |

Synthetic target agreement (unique SUM mode):

| Encoding | Instructed | Arithmetic | Rubric lookup |
| --- | ---: | ---: | ---: |
| numeric | 9/9 | 9/9 | 21/21 |
| fixed | 9/9 | 7/9 | 21/21 |
| symbol | 9/9 | 8/9 | 19/21 |
| anchor | 9/9 | 8/9 | 19/21 |
| numeric_ended | 9/9 | 3/9 | 21/21 |
| numeric_space | 9/9 | 9/9 | 21/21 |
| symbol_rotate | 9/9 | 6/9 | 16/21 |
| symbol_list_reverse | 9/9 | 8/9 | 15/21 |

Token-count associations with SUM scores (within request):

| Encoding | Defined / total rows | Mean Pearson r | Min r | Max r |
| --- | ---: | ---: | ---: | ---: |
| numeric | 11/39 | -0.1417 | -0.9876 | 0.7555 |
| fixed | 0/39 | undefined | undefined | undefined |
| symbol | 0/39 | undefined | undefined | undefined |
| anchor | 0/39 | undefined | undefined | undefined |
| numeric_ended | 11/39 | -0.0258 | -0.8783 | 0.7859 |
| numeric_space | 0/39 | undefined | undefined | undefined |
| numeric_api_reverse | 11/39 | -0.1415 | -0.9876 | 0.7555 |
| symbol_rotate | 0/39 | undefined | undefined | undefined |
| symbol_list_reverse | 0/39 | undefined | undefined | undefined |
| numeric_raw | 11/39 | -0.1417 | -0.9876 | 0.7555 |
| numeric_fine | 9/9 | -0.2531 | -0.6182 | -0.0070 |

Equal counts make this correlation undefined. These correlations are descriptive and confounded by intended value and task; they are not causal estimates of length bias. Per-pair token-count delta versus SUM-score delta correlations are retained in comparisons.json.

Control maximum absolute SUM-score differences: `{"numeric_api_reverse": {"pairs": 39, "max_absolute_sum_score_delta": 0.016796328707505026}, "numeric_raw": {"pairs": 39, "max_absolute_sum_score_delta": 0.0}}`.


Paraphrased service reports (separate ordinal suite):

| Encoding | Unique SUM mode matches assigned target | SUM to MEAN mode changes |
| --- | ---: | ---: |
| numeric | 16/21 | 0 |
| fixed | 14/21 | 0 |
| symbol | 15/21 | 0 |
| anchor | 14/21 | 0 |
| numeric_ended | 13/21 | 2 |
| numeric_space | 15/21 | 0 |
| numeric_api_reverse | 16/21 | 0 |
| symbol_rotate | 12/21 | 0 |
| symbol_list_reverse | 11/21 | 0 |
| numeric_raw | 16/21 | 0 |

| Paraphrase comparison | Pairs | Mode changes | Median changes | Mean TV | Max TV |
| --- | ---: | ---: | ---: | ---: | ---: |
| numeric:sum -> fixed:sum | 21 | 6 | 7 | 0.234565 | 0.633987 |
| numeric:sum -> symbol:sum | 21 | 7 | 4 | 0.233059 | 0.544424 |
| numeric:sum -> anchor:sum | 21 | 8 | 9 | 0.303452 | 0.733321 |
| numeric:sum -> numeric_ended:sum | 21 | 8 | 9 | 0.274245 | 0.691433 |
| numeric:sum -> numeric_space:sum | 21 | 3 | 3 | 0.141792 | 0.365587 |
| numeric:sum -> numeric_api_reverse:sum | 21 | 0 | 0 | 0.000018 | 0.000383 |
| symbol:sum -> symbol_rotate:sum | 21 | 10 | 8 | 0.256510 | 0.745606 |
| symbol:sum -> symbol_list_reverse:sum | 21 | 8 | 11 | 0.278917 | 0.728924 |
| numeric:sum -> numeric_raw:sum | 21 | 0 | 0 | 0.000000 | 0.000000 |

Paraphrase targets are author-assigned ordinal rubric expectations, not independently adjudicated human ratings. No interval summaries are computed.

## Qwen3.8-27B-Ridge-3.7bpw

Completed 399 matrix rows; 399 successful; 0 errors.

SUM comparisons use total variation distance (TV), from 0 to 1, after aligning by numeric value. The interval mean shift is reported only for interval cases.

| Comparison | Pairs | Mode changes | Median changes | Mean TV | Max TV | Max absolute interval mean shift |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| numeric:sum -> fixed:sum | 39 | 4 | 4 | 0.068897 | 0.517252 | 4.654582 |
| numeric:sum -> symbol:sum | 39 | 5 | 4 | 0.135039 | 0.949353 | 4.646515 |
| numeric:sum -> anchor:sum | 39 | 4 | 4 | 0.095292 | 0.692047 | 4.654601 |
| numeric:sum -> numeric_ended:sum | 39 | 18 | 20 | 0.557954 | 0.998670 | 4.013103 |
| numeric:sum -> numeric_space:sum | 39 | 2 | 2 | 0.110304 | 0.965985 | 3.603140 |
| numeric:sum -> numeric_api_reverse:sum | 39 | 0 | 0 | 0.000000 | 0.000000 | 0.000000 |
| symbol:sum -> symbol_rotate:sum | 39 | 3 | 2 | 0.102441 | 0.928009 | 0.585803 |
| symbol:sum -> symbol_list_reverse:sum | 39 | 4 | 3 | 0.095451 | 0.788964 | 0.922311 |
| numeric:sum -> numeric_raw:sum | 39 | 0 | 0 | 0.000000 | 0.000000 | 0.000000 |
| numeric:sum -> numeric_fine:sum | 9 | 1 | 1 | 0.065582 | 0.228095 | 0.562305 |

SUM versus MEAN on the same scored rows:

| Representation | Cases | Mode changes | Median changes | Mean TV | Max TV |
| --- | ---: | ---: | ---: | ---: | ---: |
| numeric | 39 | 2 | 2 | 0.012369 | 0.177071 |
| fixed | 39 | 0 | 0 | 0.167730 | 0.376703 |
| symbol | 39 | 0 | 0 | 0.000000 | 0.000000 |
| anchor | 39 | 0 | 1 | 0.024363 | 0.172752 |
| numeric_ended | 39 | 17 | 22 | 0.437309 | 0.871251 |
| numeric_space | 39 | 11 | 13 | 0.356910 | 0.835170 |
| numeric_api_reverse | 39 | 2 | 2 | 0.012369 | 0.177071 |
| symbol_rotate | 39 | 0 | 0 | 0.000000 | 0.000000 |
| symbol_list_reverse | 39 | 0 | 0 | 0.000000 | 0.000000 |
| numeric_raw | 39 | 2 | 2 | 0.012369 | 0.177071 |
| numeric_fine | 9 | 0 | 1 | 0.195063 | 0.442362 |

Tokenization of the five main encodings:

| Scale | Encoding | Token counts in value order | Strict-prefix pairs |
| --- | --- | --- | --- |
| 0_10 | numeric | [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2] | [["1", "10"]] |
| 0_10 | fixed | [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2] | [] |
| 0_10 | symbol | [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1] | [] |
| 0_10 | anchor | [1, 1, 2, 1, 1, 1, 1, 1, 1, 2, 1] | [] |
| 0_10 | numeric_ended | [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3] | [] |
| 1_5 | numeric | [1, 1, 1, 1, 1] | [] |
| 1_5 | fixed | [2, 2, 2, 2, 2] | [] |
| 1_5 | symbol | [1, 1, 1, 1, 1] | [] |
| 1_5 | anchor | [1, 2, 1, 1, 1] | [] |
| 1_5 | numeric_ended | [2, 2, 2, 2, 2] | [] |
| minus2_2 | numeric | [2, 2, 1, 1, 1] | [] |
| minus2_2 | fixed | [3, 3, 3, 3, 3] | [] |
| minus2_2 | symbol | [1, 1, 1, 1, 1] | [] |
| minus2_2 | anchor | [1, 2, 1, 1, 1] | [] |
| minus2_2 | numeric_ended | [3, 3, 2, 2, 2] | [] |

Synthetic target agreement (unique SUM mode):

| Encoding | Instructed | Arithmetic | Rubric lookup |
| --- | ---: | ---: | ---: |
| numeric | 8/9 | 7/9 | 20/21 |
| fixed | 9/9 | 9/9 | 21/21 |
| symbol | 9/9 | 7/9 | 20/21 |
| anchor | 9/9 | 9/9 | 21/21 |
| numeric_ended | 8/9 | 5/9 | 5/21 |
| numeric_space | 8/9 | 6/9 | 20/21 |
| symbol_rotate | 9/9 | 8/9 | 20/21 |
| symbol_list_reverse | 9/9 | 9/9 | 20/21 |

Token-count associations with SUM scores (within request):

| Encoding | Defined / total rows | Mean Pearson r | Min r | Max r |
| --- | ---: | ---: | ---: | ---: |
| numeric | 28/39 | -0.1616 | -0.7667 | 0.7125 |
| fixed | 0/39 | undefined | undefined | undefined |
| symbol | 0/39 | undefined | undefined | undefined |
| anchor | 39/39 | -0.2095 | -0.7697 | 0.9710 |
| numeric_ended | 28/39 | -0.1392 | -0.8683 | 0.5556 |
| numeric_space | 17/39 | -0.3222 | -0.7247 | 0.6228 |
| numeric_api_reverse | 28/39 | -0.1616 | -0.7667 | 0.7125 |
| symbol_rotate | 0/39 | undefined | undefined | undefined |
| symbol_list_reverse | 0/39 | undefined | undefined | undefined |
| numeric_raw | 28/39 | -0.1616 | -0.7667 | 0.7125 |
| numeric_fine | 9/9 | -0.6991 | -0.8661 | -0.2629 |

Equal counts make this correlation undefined. These correlations are descriptive and confounded by intended value and task; they are not causal estimates of length bias. Per-pair token-count delta versus SUM-score delta correlations are retained in comparisons.json.

Control maximum absolute SUM-score differences: `{"numeric_api_reverse": {"pairs": 39, "max_absolute_sum_score_delta": 0.0}, "numeric_raw": {"pairs": 39, "max_absolute_sum_score_delta": 0.0}}`.


Paraphrased service reports (separate ordinal suite):

| Encoding | Unique SUM mode matches assigned target | SUM to MEAN mode changes |
| --- | ---: | ---: |
| numeric | 19/21 | 0 |
| fixed | 19/21 | 0 |
| symbol | 16/21 | 0 |
| anchor | 18/21 | 0 |
| numeric_ended | 8/21 | 10 |
| numeric_space | 18/21 | 7 |
| numeric_api_reverse | 19/21 | 0 |
| symbol_rotate | 15/21 | 0 |
| symbol_list_reverse | 16/21 | 0 |
| numeric_raw | 19/21 | 0 |

| Paraphrase comparison | Pairs | Mode changes | Median changes | Mean TV | Max TV |
| --- | ---: | ---: | ---: | ---: | ---: |
| numeric:sum -> fixed:sum | 21 | 2 | 2 | 0.077243 | 0.514356 |
| numeric:sum -> symbol:sum | 21 | 7 | 7 | 0.227999 | 0.801950 |
| numeric:sum -> anchor:sum | 21 | 3 | 3 | 0.146406 | 0.827696 |
| numeric:sum -> numeric_ended:sum | 21 | 13 | 13 | 0.598467 | 0.974446 |
| numeric:sum -> numeric_space:sum | 21 | 1 | 2 | 0.126960 | 0.832217 |
| numeric:sum -> numeric_api_reverse:sum | 21 | 0 | 0 | 0.000000 | 0.000000 |
| symbol:sum -> symbol_rotate:sum | 21 | 7 | 5 | 0.246842 | 0.807170 |
| symbol:sum -> symbol_list_reverse:sum | 21 | 1 | 4 | 0.121196 | 0.450457 |
| numeric:sum -> numeric_raw:sum | 21 | 0 | 0 | 0.000000 | 0.000000 |

Paraphrase targets are author-assigned ordinal rubric expectations, not independently adjudicated human ratings. No interval summaries are computed.


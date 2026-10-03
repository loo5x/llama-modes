# llama-modes cookbook

These recipes target `http://127.0.0.1:8080` with a loaded GGUF and a llama-modes server. JSON requests are complete bodies for the named endpoint; send with `Content-Type: application/json`. Save a body as `request.json`, then run `curl.exe --fail-with-body http://127.0.0.1:8080/decision -H "Content-Type: application/json" --data-binary "@request.json"` on Windows, changing the endpoint for SCALE. [Runnable examples](../examples/README-modes.md) provide Python, PowerShell, and POSIX curl alternatives.

**All representative responses below are illustrative schema examples, not measured results. Token IDs and numbers are invented only to explain the format, explicitly not performance evidence.** Excerpts are labeled; actual responses contain every requested row and the complete fields described in [Decision](decision.md) and [SCALE](scale.md). Relative weights are never calibrated confidence. Unless stated otherwise, direct requests generate zero answer tokens by design.

For several independent questions about one text, v0.5.0 adds [`/evaluate`](evaluate.md), which orchestrates these same three scoring primitives. See the [shared-context quickstart](quickstart.md#8-v05-multiple-questions-optional) for a complete request and opt-in prefix reuse. The recipes below use the individual scoring endpoints.

## 1. Boolean fact judgment

### Goal

Get a Yes/No preference for a factual statement.

### When to use it

You need a structured fact judgment and have task-specific evaluation to assess reliability.

### Complete request

`POST /decision`

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Is Paris the capital of France? Return only Yes or No."
    }
  ],
  "choices": [
    "Yes",
    "No"
  ]
}
```

### Representative response

Illustrative response; not live inference.

```json
{
  "choices": [
    {
      "text": "Yes",
      "token_id": 123,
      "logit": 2.0986122887,
      "probability": 0.75
    },
    {
      "text": "No",
      "token_id": 456,
      "logit": 1,
      "probability": 0.25
    }
  ]
}
```

### How to interpret it

Yes has 75% of the weight among these two candidate tokens in this illustrative response. It is not a 75% probability that the statement is true.

### Pitfalls

Token IDs and even token counts vary by model. If either label is multi-token, read SUM/MEAN scores instead of probability. A factual answer can still be wrong.

### Useful variation

Reverse the API choice order without changing the prompt to check candidate-order invariance.

## 2. Boolean policy/rule judgment

### Goal

Check whether an input satisfies a fully specified rule.

### When to use it

The rule is explicit and the model is assisting a review process.

### Complete request

`POST /decision`

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Rule: a support ticket is urgent only if the service is unavailable to every user. Ticket: Export fails, but all other features work. Does this meet the urgent rule? Return only Yes or No."
    }
  ],
  "choices": [
    "Yes",
    "No"
  ]
}
```

### Representative response

Illustrative response; not live inference.

```json
{
  "choices": [
    {
      "text": "Yes",
      "token_id": 123,
      "logit": 1,
      "probability": 0.25
    },
    {
      "text": "No",
      "token_id": 456,
      "logit": 2.0986122887,
      "probability": 0.75
    }
  ]
}
```

### How to interpret it

The rule has a narrower definition than everyday urgency. Evaluate the model against that rule, not a vague sentiment impression.

### Pitfalls

A relative weight is not an audit or proof of policy compliance. Include exceptions and scope explicitly.

### Useful variation

Add a clearly stated exception and compare results on a labeled test set.

## 3. Choice among cities/classes

### Goal

Rank a supplied categorical set.

### When to use it

Your application has known labels, such as city names or routing categories.

### Complete request

`POST /decision`

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Which city is the capital of France? Return exactly Paris, London, or New York."
    }
  ],
  "choices": [
    "Paris",
    "London",
    "New York"
  ]
}
```

### Representative response

Illustrative response; not live inference.

```json
{
  "choices": [
    {
      "text": "Paris",
      "token_ids": [
        123
      ],
      "token_count": 1,
      "sum_log_probability": -1.2,
      "mean_log_probability": -1.2
    },
    {
      "text": "London",
      "token_ids": [
        456
      ],
      "token_count": 1,
      "sum_log_probability": -4,
      "mean_log_probability": -4
    },
    {
      "text": "New York",
      "token_ids": [
        789,
        790
      ],
      "token_count": 2,
      "sum_log_probability": -5,
      "mean_log_probability": -2.5
    }
  ]
}
```

### How to interpret it

Paris has the largest SUM log probability here. A sequence response is used for every row if any label has multiple tokens.

### Pitfalls

An API list of choices does not itself tell the model their task meaning. Include the candidate meanings or list in the prompt. SUM favors continuation likelihood, not factual correctness.

### Useful variation

Replace city names with ticket classes such as billing, technical support, and account access.

## 4. Multi-token choices

### Goal

Score natural text labels without forcing a one-token vocabulary.

### When to use it

Your categories have meaningful multiword names.

### Complete request

`POST /decision`

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Route this ticket: I cannot log into my account. Choose exactly one: billing question, account access, technical issue."
    }
  ],
  "choices": [
    "billing question",
    "account access",
    "technical issue"
  ]
}
```

### Representative response

Illustrative response; not live inference.

```json
{
  "choices": [
    {
      "text": "billing question",
      "token_ids": [
        11,
        12
      ],
      "token_count": 2,
      "sum_log_probability": -6,
      "mean_log_probability": -3
    },
    {
      "text": "account access",
      "token_ids": [
        21,
        22
      ],
      "token_count": 2,
      "sum_log_probability": -1,
      "mean_log_probability": -0.5
    },
    {
      "text": "technical issue",
      "token_ids": [
        31,
        32
      ],
      "token_count": 2,
      "sum_log_probability": -4,
      "mean_log_probability": -2
    }
  ]
}
```

### How to interpret it

The model evaluates each supplied continuation with its preceding label tokens forced. No free-form answer is generated.

### Pitfalls

Longer labels tend to accumulate more negative SUM scores. MEAN is a heuristic, not sequence probability. Prefix-sharing continuations can overlap.

### Useful variation

Try equal-length symbolic labels with explicit semantic mappings, and measure whether decisions change.

## 5. Sentiment / favorability from 0 to 10

### Goal

Read all point weights for a comment rather than one generated rating.

### When to use it

You have defined a favorability rubric and explicitly accept interval distances for an expected value.

### Complete request

`POST /scale`

```json
{
  "messages": [
    {
      "role": "user",
      "content": "How favorable is this comment from 0 very unfavorable through 5 neutral to 10 very favorable? Comment: Thoughtfully designed, easy to use, and worth recommending. Return one label. Mapping: A=0, B=1, C=2, D=3, E=4, F=5, G=6, H=7, I=8, J=9, K=10"
    }
  ],
  "measurement": "interval",
  "scale": [
    {
      "value": 0,
      "label": "A"
    },
    {
      "value": 1,
      "label": "B"
    },
    {
      "value": 2,
      "label": "C"
    },
    {
      "value": 3,
      "label": "D"
    },
    {
      "value": 4,
      "label": "E"
    },
    {
      "value": 5,
      "label": "F"
    },
    {
      "value": 6,
      "label": "G"
    },
    {
      "value": 7,
      "label": "H"
    },
    {
      "value": 8,
      "label": "I"
    },
    {
      "value": 9,
      "label": "J"
    },
    {
      "value": 10,
      "label": "K"
    }
  ]
}
```

### Representative response

Illustrative excerpt; not live inference.

```json
{
  "measurement": "interval",
  "mode": [
    9
  ],
  "median": 9,
  "quantiles": {
    "0.25": 8,
    "0.75": 9
  },
  "expected_value": 8.7,
  "standard_deviation": 0.7810249676
}
```

### How to interpret it

For illustrative weights 7:0.1, 8:0.2, 9:0.6, 10:0.1 (zero elsewhere), the expected value is 8.7. Read actual points in the full response; the mean is derived from the distribution.

### Pitfalls

Literal 0..10 can fail: in the observed Qwen-style case, '1' tokenizes as a strict prefix of '10'. A..K may avoid that collision but is not universally unbiased or token-prefix-safe. A rating scale is not automatically interval.

### Useful variation

Set measurement to ordinal to retain mode, median, and quartiles without arithmetic summaries.

## 6. Likert 1-5 scale

### Goal

Represent an ordered agreement judgment.

### When to use it

You are interpreting evidence against a clear agreement statement.

### Complete request

`POST /scale`

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Rate agreement with 'The instructions were clear', based on this feedback: I understood most steps but needed help at the end. 1 strongly disagree; 2 disagree; 3 neither agree nor disagree; 4 agree; 5 strongly agree. Return one label. Mapping: A=1, B=2, C=3, D=4, E=5"
    }
  ],
  "measurement": "ordinal",
  "scale": [
    {
      "value": 1,
      "label": "A"
    },
    {
      "value": 2,
      "label": "B"
    },
    {
      "value": 3,
      "label": "C"
    },
    {
      "value": 4,
      "label": "D"
    },
    {
      "value": 5,
      "label": "E"
    }
  ]
}
```

### Representative response

Illustrative excerpt; not live inference.

```json
{
  "measurement": "ordinal",
  "mode": [
    4
  ],
  "median": 4,
  "quantiles": {
    "0.25": 3,
    "0.75": 4
  }
}
```

### How to interpret it

Categories are ordered, but equal numerical distances have not been assumed. An ordinal response intentionally omits expected_value and standard_deviation.

### Pitfalls

The model is rating the supplied evidence; it is not collecting a person's own survey response. Do not infer population opinion.

### Useful variation

Add concrete examples for each anchor and evaluate agreement with independently assigned labels.

## 7. Severity / risk scale

### Goal

Order fictional support incidents by a stated impact rubric.

### When to use it

You want triage assistance with explicit categories, followed by appropriate human review.

### Complete request

`POST /scale`

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Rate this fictional support incident. 0 no impact; 1 cosmetic defect; 2 one feature unavailable; 3 whole service unavailable. Incident: The export button fails, but users can work normally otherwise. Return one label. Mapping: A=0, B=1, C=2, D=3"
    }
  ],
  "measurement": "ordinal",
  "scale": [
    {
      "value": 0,
      "label": "A"
    },
    {
      "value": 1,
      "label": "B"
    },
    {
      "value": 2,
      "label": "C"
    },
    {
      "value": 3,
      "label": "D"
    }
  ]
}
```

### Representative response

Illustrative excerpt; not live inference.

```json
{
  "measurement": "ordinal",
  "mode": [
    2
  ],
  "median": 2,
  "quantiles": {
    "0.25": 2,
    "0.75": 2
  }
}
```

### How to interpret it

The result concerns the stated operational rubric. Concentration on a category is model preference, not an independently validated estimate of risk.

### Pitfalls

Do not silently repurpose these weights as safety or medical risk probabilities. Ambiguous impact descriptions need more information.

### Useful variation

Replace the rubric with your own documented incident classes, retaining ordinal measurement.

## 8. Ordinal versus interval SCALE

### Goal

Choose summaries that match your measurement assumptions.

### When to use it

You have ordered points and must decide whether differences between their numbers mean anything.

### Complete request

`POST /scale`

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Select the delivery delay category for a package arriving exactly three days late. Label A, category value 0: on time. Label B, category value 1: one day late. Label C, category value 2: three days late. Return A, B, or C."
    }
  ],
  "measurement": "ordinal",
  "scale": [
    {
      "value": 0,
      "label": "A"
    },
    {
      "value": 1,
      "label": "B"
    },
    {
      "value": 2,
      "label": "C"
    }
  ]
}
```

### Representative response

Illustrative excerpt; not live inference.

```json
{
  "measurement": "ordinal",
  "mode": [
    2
  ],
  "median": 2,
  "quantiles": {
    "0.25": 2,
    "0.75": 2
  }
}
```

### How to interpret it

Here values 0,1,2 encode order and C denotes three days late; they are category codes, not day counts. Use ordinal summaries.

### Pitfalls

Changing only measurement to interval would assert equally spaced category codes. It would not convert them into actual day counts.

### Useful variation

For an interval day-count scale, change the third point value to 3, explicitly map A=0 days, B=1 day, C=3 days in the prompt, and set measurement to interval. Expected delay then uses day units.

## 9. Batch evaluation of many inputs

### Goal

Evaluate a list of inputs with a stable task definition.

### When to use it

You need repeatable per-input records. The `/decision` endpoint accepts one prompt/conversation per request, not a batch array. For multiple questions about a single context, use `/evaluate`; that is distinct from batching unrelated inputs.

### Complete request

```python
import json
import urllib.request

questions = ["Is Paris the capital of France?", "Is 2 an odd number?"]
for index, question in enumerate(questions):
    body = {"messages": [{"role": "user", "content": question + " Return only Yes or No."}], "choices": ["Yes", "No"]}
    req = urllib.request.Request("http://127.0.0.1:8080/decision", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as response:
        print(json.dumps({"id": index, "request": body, "response": json.load(response)}))
```

### Representative response

Illustrative excerpt; not live inference.

```json
{
  "id": 0,
  "response": {
    "choices": [
      {
        "text": "Yes",
        "probability": 0.75
      },
      {
        "text": "No",
        "probability": 0.25
      }
    ]
  }
}
```

### How to interpret it

Each row preserves the association between one input and its result. This simple example stops on an HTTP error; the benchmark harness records failures and continues after warmup.

### Pitfalls

Submitting a JSON list as the request body is not supported. Concurrent GPU requests also make simple latency comparisons harder to interpret.

### Useful variation

Use external JSONL and the benchmark harness for repeated runs and saved errors.

## 10. Comparing two models

### Goal

Compare model behavior on identical tasks.

### When to use it

You can load the models one at a time using the same build and controlled settings.

### Complete request

```python
import json
import urllib.request

body = {"messages": [{"role": "user", "content": "Which city is the capital of France? Return only Paris, London, or New York."}], "choices": ["Paris", "London", "New York"]}
req = urllib.request.Request("http://127.0.0.1:8080/decision", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
with urllib.request.urlopen("http://127.0.0.1:8080/v1/models", timeout=10) as response:
    model = json.load(response)
with urllib.request.urlopen(req, timeout=120) as response:
    print(json.dumps({"model": model, "request": body, "response": json.load(response)}, indent=2))
```

### Representative response

Illustrative response; not live inference.

```json
{
  "choices": [
    {
      "text": "Paris",
      "token_ids": [
        123
      ],
      "token_count": 1,
      "sum_log_probability": -1.2,
      "mean_log_probability": -1.2
    },
    {
      "text": "London",
      "token_ids": [
        456
      ],
      "token_count": 1,
      "sum_log_probability": -4,
      "mean_log_probability": -4
    },
    {
      "text": "New York",
      "token_ids": [
        789,
        790
      ],
      "token_count": 2,
      "sum_log_probability": -5,
      "mean_log_probability": -2.5
    }
  ]
}
```

### How to interpret it

Run the complete request with model A loaded and save the output, then stop/reload with model B and repeat. Compare rankings, task correctness, and representation sensitivity before comparing score magnitudes.

### Pitfalls

Different tokenizers and templates mean raw likelihoods are not directly comparable measures of confidence across models. Do not run both GPU workloads together for a timing claim.

### Useful variation

Run the benchmark twice with separate output directories and recorded model/runtime hashes.

## 11. Raw prompt mode

### Goal

Evaluate an explicitly prepared response boundary.

### When to use it

You understand the target model's prompt format or are testing raw completion behavior.

### Complete request

`POST /decision`

```json
{
  "prompt": "Answer yes or no: Is Paris the capital of France?\nAnswer:",
  "choices": [
    " yes",
    " no"
  ]
}
```

### Representative response

Illustrative response; not live inference.

```json
{
  "choices": [
    {
      "text": " yes",
      "token_id": 123,
      "logit": 2.0986122887,
      "probability": 0.75
    },
    {
      "text": " no",
      "token_id": 456,
      "logit": 1,
      "probability": 0.25
    }
  ]
}
```

### How to interpret it

No template is applied. Leading spaces are part of the independently tokenized labels.

### Pitfalls

A syntactically accepted raw prompt is not necessarily a suitable instruction prompt for a chat model. GPT-OSS requires a final-content boundary for the validated direct readout; an assistant role marker alone was misleading.

### Useful variation

Use the native messages recipe unless you need to control or compare exact prepared prompt tokens.

## 12. Native messages mode

### Goal

Let the server apply the model's native template at the assistant content boundary.

### When to use it

You have a text conversation ending in a user message.

### Complete request

`POST /decision`

```json
{
  "messages": [
    {
      "role": "system",
      "content": "Apply the stated rule literally."
    },
    {
      "role": "user",
      "content": "Rule: accept only even integers. Is 8 acceptable? Return only Yes or No."
    }
  ],
  "choices": [
    "Yes",
    "No"
  ]
}
```

### Representative response

Illustrative response; not live inference.

```json
{
  "choices": [
    {
      "text": "Yes",
      "token_id": 123,
      "logit": 2.0986122887,
      "probability": 0.75
    },
    {
      "text": "No",
      "token_id": 456,
      "logit": 1,
      "probability": 0.25
    }
  ]
}
```

### How to interpret it

The server prepares content-entry semantics for direct evaluation. This differs from normal chat that may generate reasoning before its answer.

### Pitfalls

Templates can reject unsupported roles or ambiguous boundaries. Messages only accept role and text content; tools, images, reasoning fields, and assistant continuation are unsupported. Do not supply prompt alongside messages.

### Useful variation

Remove the system message if the native template does not support it, placing the complete instruction in the user message.

## 13. Handling scale prefix-token rejection

### Goal

Recognize and repair an encoding collision without changing the scale's meaning.

### When to use it

The server returns HTTP 400 for strict token-prefix overlap.

### Complete request

`POST /scale`

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Select the score for an excellent result: 1 poor, 10 excellent. Return 1 or 10."
    }
  ],
  "measurement": "ordinal",
  "scale": [
    {
      "value": 1,
      "label": "1"
    },
    {
      "value": 10,
      "label": "10"
    }
  ]
}
```

### Representative response

Illustrative excerpt; not live inference.

```json
{
  "error": {
    "message": "Scale labels must not have strict token-prefix overlap"
  }
}
```

### How to interpret it

For the observed Qwen-style tokenizer, the token sequence for 1 is a strict prefix of that for 10. The response is a representation validation failure, not a model judgment.

### Pitfalls

This request need not fail on every tokenizer. String-prefix tests cannot substitute for token-prefix checks. Do not remove the error by silently dropping a point.

### Useful variation

Resubmit with points {value:1,label:"A"} and {value:10,label:"B"}; rewrite the message to say A=1 poor and B=10 excellent. Verify this new mapping with the model.

## 14. Inspecting raw log probabilities

### Goal

Understand the likelihood components instead of treating every score as a confidence number.

### When to use it

You are debugging label length or representation effects.

### Complete request

`POST /decision`

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Which city is the capital of France? Return only Paris, London, or New York."
    }
  ],
  "choices": [
    "Paris",
    "London",
    "New York"
  ]
}
```

### Representative response

Illustrative response; not live inference.

```json
{
  "choices": [
    {
      "text": "Paris",
      "token_ids": [
        123
      ],
      "token_count": 1,
      "sum_log_probability": -1.2,
      "mean_log_probability": -1.2
    },
    {
      "text": "London",
      "token_ids": [
        456
      ],
      "token_count": 1,
      "sum_log_probability": -4,
      "mean_log_probability": -4
    },
    {
      "text": "New York",
      "token_ids": [
        789,
        790
      ],
      "token_count": 2,
      "sum_log_probability": -5,
      "mean_log_probability": -2.5
    }
  ]
}
```

### How to interpret it

New York's SUM -5 and token count 2 imply MEAN -2.5. SUM is the natural log likelihood of its continuation, without an EOS requirement. The sequence scorer normalizes each step over the full vocabulary.

### Pitfalls

The single-token fast path returns only logits and candidate-relative probabilities, not full-vocabulary log probabilities. Taking log of its relative probability does not recover the absolute vocabulary-normalized value.

### Useful variation

Inspect SCALE raw point scores, which always use full-vocabulary sequence scoring, when your task is genuinely an ordered prefix-free scale. Do not add a meaningless diagnostic choice to a production task without documenting the change.

## 15. Choosing good label representations

### Goal

Make the task-to-label mapping clear and test representation sensitivity.

### When to use it

Labels have unequal lengths, prefixes, ambiguous meanings, or unwanted formatting.

### Complete request

`POST /decision`

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Classify the support request: I need a copy of my invoice. Mapping: A=billing question; B=account access; C=technical issue. Return exactly A, B, or C."
    }
  ],
  "choices": [
    "A",
    "B",
    "C"
  ]
}
```

### Representative response

Illustrative response; not live inference.

```json
{
  "choices": [
    {
      "text": "A",
      "token_id": 11,
      "logit": 2.3862943611,
      "probability": 0.6666666667
    },
    {
      "text": "B",
      "token_id": 12,
      "logit": 1,
      "probability": 0.1666666667
    },
    {
      "text": "C",
      "token_id": 13,
      "logit": 1,
      "probability": 0.1666666666
    }
  ]
}
```

### How to interpret it

Symbols can reduce length differences, but their meanings come entirely from the explicit mapping. Score labels, then map them back to your categories.

### Pitfalls

Symbols can have prior preferences too. Equal token count is not proof of fairness. Reversing API order holds the prompt fixed; reversing the mapping in the prompt changes the prompt and tests a different sensitivity.

### Useful variation

Rotate label assignments while preserving category meanings and compare mapped results on the same labeled dataset. Record all variants rather than choosing only the favorable encoding.

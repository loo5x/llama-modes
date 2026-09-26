import pytest
import requests
import time
import random
import math
import socket
from pathlib import Path

from openai import OpenAI
from utils import *

server = ServerPreset.tinyllama2()

JSON_MULTIMODAL_KEY = "multimodal_data"
JSON_PROMPT_STRING_KEY = "prompt_string"


def test_decision_raw():
    server.start()
    request = {"prompt": "Answer yes or no: Is water wet?\nAnswer:", "choices": ["yes", "no"]}
    response = server.make_request("POST", "/decision", request)
    assert response.status_code == 200
    assert set(response.body) == {"choices"}
    choices = response.body["choices"]
    assert len(choices) == 2
    weights = [math.exp(c["logit"] - max(c["logit"] for c in choices)) for c in choices]
    for text, choice, weight in zip(request["choices"], choices, weights):
        assert set(choice) == {"text", "token_id", "logit", "probability"}
        assert choice["text"] == text
        tokens = server.make_request("POST", "/tokenize", {
            "content": text, "add_special": False, "parse_special": False,
        })
        assert tokens.status_code == 200
        assert tokens.body["tokens"] == [choice["token_id"]]
        assert choice["probability"] == pytest.approx(weight / sum(weights))
    repeated = server.make_request("POST", "/v1/decision", request)
    assert repeated.status_code == 200
    assert len(repeated.body["choices"]) == 2
    for first, second in zip(choices, repeated.body["choices"]):
        assert first["token_id"] == second["token_id"]
        assert first["logit"] == pytest.approx(second["logit"], abs=1e-4)


def test_decision_invalid_requests():
    server.start()
    messages = [{"role": "user", "content": "Hello"}]
    valid = server.make_request("POST", "/decision", {"prompt": "Hello", "choices": ["yes", "no"]})
    assert valid.status_code == 200
    assert len(valid.body["choices"]) == 2
    invalid = [
        {"prompt": "Hello", "messages": messages},
        {},
        {"prompt": ""},
        {"prompt": 12},
        {"messages": []},
        {"messages": "Hello"},
        {"messages": [{"role": "assistant", "content": "Hello"}]},
        {"messages": [{"role": "system", "content": "Hello"}]},
        {"messages": [{"role": "tool", "content": "Hello"}]},
        {"messages": [None]},
        {"messages": [{"role": "user", "content": None}]},
        {"messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "invalid"}}]}]},
        {"messages": [{"role": "assistant", "content": "", "tool_calls": []}] + messages},
        {"messages": [{"role": "assistant", "content": "Hello", "reasoning_content": "Thinking"}] + messages},
    ]
    for extra in ({"tools": []}, {"stream": False}, {"reasoning_effort": "none"},
                  {"chat_template_kwargs": {}}, {"continue_final_message": False},
                  {"grammar": ""}, {"response_format": {"type": "text"}}):
        invalid.append({"messages": messages, **extra})
    for request in invalid:
        response = server.make_request("POST", "/decision", {**request, "choices": ["yes", "no"]})
        assert response.status_code == 400, request
    for source in ({"prompt": "Hello"}, {"messages": messages}):
        missing = server.make_request("POST", "/decision", source)
        assert missing.status_code == 400
        for choices in ([], [""], [12], ["yes", "yes"]):
            response = server.make_request("POST", "/decision", {**source, "choices": choices})
            assert response.status_code == 400, choices


def decision_tokens(text, prompt=False):
    response = server.make_request("POST", "/tokenize", {
        "content": text, "add_special": prompt, "parse_special": prompt,
    })
    assert response.status_code == 200
    return response.body["tokens"]


def decision_metrics():
    response = requests.get(server.make_url("/metrics"), timeout=10)
    assert response.status_code == 200
    return {line.split()[0]: float(line.split()[1]) for line in response.text.splitlines()
            if line.startswith("llamacpp:")}


@pytest.mark.parametrize("batch_size", [1, 7, 32])
def test_decision_teacher_forced_oracle(tmp_path, batch_size):
    server.n_slots = 1
    server.n_batch = batch_size
    server.n_ubatch = batch_size
    server.n_gpu_layer = int(os.environ.get("N_GPU_LAYERS", "0"))
    server.fa = "off"
    server.server_metrics = True
    server.start()
    executable = os.environ.get("LLAMA_TEST_STATE_BIN_PATH")
    if not executable:
        suffix = ".exe" if os.name == "nt" else ""
        executable = str(Path(server.process.args[0]).with_name("test-save-load-state" + suffix))
    assert Path(executable).is_file(), "Build test-save-load-state or set LLAMA_TEST_STATE_BIN_PATH"

    prompt = "Once upon a time there was a"
    texts = ["yes", "yes indeed", "yes indeed my friend", "no", " big dog", "\nhello", "caf\u00e9", "<|im_end|>"]
    tokens = [decision_tokens(text) for text in texts]
    assert len(tokens[0]) == len(tokens[3]) == 1
    assert tokens[1][:len(tokens[0])] == tokens[0]
    assert tokens[2][:len(tokens[1])] == tokens[1]
    prompt_tokens = decision_tokens(prompt, prompt=True)
    request_path = tmp_path / "oracle.json"
    output_path = tmp_path / "scores.json"
    request_path.write_text(json.dumps({
        "prompt_tokens": prompt_tokens, "choices": tokens, "output": str(output_path),
    }), encoding="utf-8")
    props = server.make_request("GET", "/props")
    assert props.status_code == 200
    large_batch = max(100, len(prompt_tokens) + max(map(len, tokens)) + 8)
    oracle_runs = []
    for oracle_batch, oracle_ubatch in [(batch_size, batch_size), (len(prompt_tokens), large_batch), (large_batch, large_batch)]:
        subprocess.run([
            executable, "-m", props.body["model_path"], "-c", str(server.n_ctx),
            "-b", str(oracle_batch), "-ub", str(oracle_ubatch), "-ngl", str(server.n_gpu_layer), "-fa", "off",
            "--decision-oracle", str(request_path),
        ], check=True, timeout=180)
        oracle_runs.append(json.loads(output_path.read_text(encoding="utf-8")))
    oracle = oracle_runs[0]
    assert len(oracle) == len(oracle_runs[1]) == len(oracle_runs[2]) == len(tokens)
    for ids, matched_batch, exact_batch, oversized_batch in zip(tokens, oracle, oracle_runs[1], oracle_runs[2]):
        assert len(matched_batch) == len(exact_batch) == len(oversized_batch) == len(ids)
        assert oversized_batch == pytest.approx(exact_batch, rel=0, abs=2e-4)

    expected = dict(zip(texts, zip(tokens, oracle)))
    n_prefills = sum(len(ids) > 1 for ids in tokens)
    n_forced = sum(len(ids) - 1 for ids in tokens)
    baseline = None
    for order in [texts, texts[::-1], texts[1:] + texts[:1], texts]:
        before = decision_metrics()
        actual = server.make_request("POST", "/decision", {"prompt": prompt, "choices": order})
        assert actual.status_code == 200
        assert len(actual.body["choices"]) == len(order)
        for result, text in zip(actual.body["choices"], order):
            ids, per_token = expected[text]
            assert set(result) == {"text", "token_ids", "token_count", "sum_log_probability", "mean_log_probability"}
            assert result["text"] == text
            assert result["token_ids"] == ids
            assert result["token_count"] == len(ids) == len(per_token)
            assert result["sum_log_probability"] == pytest.approx(math.fsum(per_token), rel=0, abs=2e-4)
            assert result["mean_log_probability"] == pytest.approx(math.fsum(per_token) / len(ids), rel=0, abs=2e-4)
        after = decision_metrics()
        assert after["llamacpp:prompt_tokens_total"] - before["llamacpp:prompt_tokens_total"] == len(prompt_tokens) * n_prefills
        assert after["llamacpp:n_decode_total"] - before["llamacpp:n_decode_total"] == math.ceil(len(prompt_tokens) / batch_size) * n_prefills + n_forced
        assert after["llamacpp:tokens_predicted_total"] == before["llamacpp:tokens_predicted_total"]
        assert after["llamacpp:spec_decode_num_draft_tokens_total"] == before["llamacpp:spec_decode_num_draft_tokens_total"]
        scores = {c["text"]: c["sum_log_probability"] for c in actual.body["choices"]}
        if baseline is None:
            baseline = scores
        assert scores == baseline

    for indices in [[0, 3], [1, 4, 5], [0, 3, 4]]:
        response = server.make_request("POST", "/scale", {
            "prompt": prompt, "measurement": "ordinal",
            "scale": [{"value": i, "label": texts[i]} for i in indices],
        })
        assert response.status_code == 200
        for point, i in zip(response.body["points"], indices):
            assert point["token_ids"] == tokens[i]
            assert point["sum_log_probability"] == pytest.approx(math.fsum(oracle[i]), rel=0, abs=2e-4)


def test_decision_context_and_resource_limits():
    server.n_slots = 1
    server.n_ctx = 128
    server.enable_ctx_shift = True
    server.server_slots = True
    server.start()
    prompt = "Once upon a time"
    prompt_length = len(decision_tokens(prompt, prompt=True))
    n_ctx = server.make_request("GET", "/slots").body[0]["n_ctx"]
    choice = " yes" * (n_ctx - prompt_length + 1)
    ids = decision_tokens(choice)
    assert prompt_length + len(ids) - 1 == n_ctx
    accepted = server.make_request("POST", "/decision", {"prompt": prompt, "choices": [choice, "yes", choice[:-4]]})
    assert accepted.status_code == 200
    assert len(accepted.body["choices"]) == 3
    assert accepted.body["choices"][0]["token_count"] == len(ids)
    rejected = server.make_request("POST", "/decision", {"prompt": prompt, "choices": [choice + " yes"]})
    assert rejected.status_code == 400
    for choices in (["x"] * 257, ["x" * (1024 * 1024 + 1)], [" yes" * 32769]):
        rejected = server.make_request("POST", "/decision", {"prompt": prompt, "choices": choices})
        assert rejected.status_code == 400
    repeated = server.make_request("POST", "/decision", {"prompt": prompt, "choices": [choice]})
    assert repeated.status_code == 200
    assert repeated.body["choices"][0]["sum_log_probability"] == pytest.approx(accepted.body["choices"][0]["sum_log_probability"], abs=2e-4)


@pytest.mark.parametrize("endpoint", ["/decision", "/scale"])
@pytest.mark.parametrize("spec_type", [None, "ngram-simple"])
def test_decision_cleanup_and_chat_regression(spec_type, endpoint):
    server.n_slots = 1
    server.spec_type = spec_type
    server.server_metrics = True
    server.chat_template = "chatml"
    server.start()
    chat = {"messages": [{"role": "user", "content": "Tell me a short story."}],
            "temperature": 0, "max_tokens": 8, "cache_prompt": False}
    first = server.make_request("POST", "/v1/chat/completions", chat)
    assert first.status_code == 200
    legacy_request = {"prompt": "Answer yes or no:", "choices": ["yes", "no"]}
    legacy_before = server.make_request("POST", "/decision", legacy_request)
    assert legacy_before.status_code == 200
    before = decision_metrics()
    request = {"prompt": "Once upon a time", "choices": ["yes", " little girl", "no", " big dog"]}
    if endpoint == "/scale":
        request = scale_request(request["choices"])
    for _ in range(2):
        result = server.make_request("POST", endpoint, request)
        assert result.status_code == 200
    after = decision_metrics()
    assert after["llamacpp:tokens_predicted_total"] == before["llamacpp:tokens_predicted_total"]
    assert after["llamacpp:spec_decode_num_draft_tokens_total"] == before["llamacpp:spec_decode_num_draft_tokens_total"]
    legacy_after = server.make_request("POST", "/decision", legacy_request)
    assert legacy_after.status_code == 200
    for a, b in zip(legacy_before.body["choices"], legacy_after.body["choices"]):
        assert set(b) == {"text", "token_id", "logit", "probability"}
        assert a["token_id"] == b["token_id"]
        assert a["logit"] == pytest.approx(b["logit"], abs=2e-4)
        assert a["probability"] == pytest.approx(b["probability"], abs=2e-4)
    second = server.make_request("POST", "/v1/chat/completions", chat)
    assert second.status_code == 200
    assert first.body["choices"] == second.body["choices"]
    assert first.body["usage"] == second.body["usage"]


@pytest.mark.parametrize("endpoint", ["/decision", "/scale"])
def test_decision_cancel_cleanup(endpoint):
    server.n_slots = 1
    server.n_ctx = 1024
    server.server_slots = True
    server.server_metrics = True
    server.start()
    before = decision_metrics()
    if endpoint == "/scale":
        request = scale_request([" yes" * 900 + chr(65 + i) for i in range(26)])
    else:
        request = {"prompt": "Once upon a time", "choices": [" yes" * 900 + str(i) for i in range(32)]}
    body = json.dumps(request).encode()
    with socket.create_connection((server.server_host, server.server_port), timeout=10) as connection:
        connection.sendall((f"POST {endpoint} HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n").encode() + body)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            slots = server.make_request("GET", "/slots")
            if slots.body[0]["is_processing"] and decision_metrics()["llamacpp:n_decode_total"] > before["llamacpp:n_decode_total"] + 5:
                break
            time.sleep(0.01)
        else:
            pytest.fail("Decision did not enter forced scoring before cancellation")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not server.make_request("GET", "/slots").body[0]["is_processing"]:
            break
        time.sleep(0.01)
    else:
        pytest.fail("Cancelled decision did not release its slot")
    after = decision_metrics()
    for key in ["llamacpp:tokens_predicted_total", "llamacpp:spec_decode_num_draft_tokens_total"]:
        assert after[key] == before[key]
    request = {"prompt": "Once upon a time", "choices": [" little girl", " big dog"]}
    if endpoint == "/scale":
        request = scale_request(request["choices"])
    first = server.make_request("POST", endpoint, request)
    second = server.make_request("POST", endpoint, request)
    assert first.status_code == second.status_code == 200
    key = "points" if endpoint == "/scale" else "choices"
    for a, b in zip(first.body[key], second.body[key]):
        assert a["sum_log_probability"] == pytest.approx(b["sum_log_probability"], abs=2e-4)


def scale_request(labels, measurement="ordinal"):
    return {"prompt": "Once upon a time", "measurement": measurement,
            "scale": [{"value": i - 1, "label": label} for i, label in enumerate(labels)]}


@pytest.mark.parametrize("measurement", ["ordinal", "interval"])
@pytest.mark.parametrize("labels", [["yes", "no"], [" little girl", " big dog"], ["yes", " big dog", "no"]])
def test_scale_scores_and_order(measurement, labels):
    server.n_slots = 1
    server.server_metrics = True
    server.start()
    request = scale_request(labels, measurement)
    ids = [decision_tokens(label) for label in labels]
    assert [len(t) == 1 for t in ids] == [label in ("yes", "no") for label in labels]
    # A multi-token choice keeps the decision reference on full-vocabulary scoring.
    reference = server.make_request("POST", "/decision", {
        "prompt": request["prompt"], "choices": labels + [" a completely different ending"],
    })
    assert reference.status_code == 200
    before = decision_metrics()
    baseline = None
    for points in [request["scale"], request["scale"][::-1], request["scale"][1:] + request["scale"][:1]]:
        response = server.make_request("POST", "/v1/scale", {**request, "scale": points})
        assert response.status_code == 200, response.body
        result = response.body
        if baseline is None:
            baseline = result
        assert result == baseline
        expected_fields = {"measurement", "points", "mode", "median", "quantiles"}
        if measurement == "interval":
            expected_fields |= {"expected_value", "standard_deviation"}
        assert set(result) == expected_fields
        assert result["measurement"] == measurement
        scores = [p["sum_log_probability"] for p in result["points"]]
        weights = [math.exp(score - max(scores)) for score in scores]
        weights = [w / math.fsum(weights) for w in weights]
        for i, (point, ref) in enumerate(zip(result["points"], reference.body["choices"])):
            assert set(point) == {"value", "label", "token_ids", "token_count", "sum_log_probability",
                                  "mean_log_probability", "relative_weight", "cumulative_weight"}
            assert point["value"] == i - 1
            assert point["label"] == labels[i]
            assert point["token_ids"] == ids[i]
            assert point["token_count"] == len(ids[i])
            assert point["sum_log_probability"] == pytest.approx(ref["sum_log_probability"], abs=2e-4)
            assert point["mean_log_probability"] == pytest.approx(scores[i] / len(ids[i]))
            assert point["relative_weight"] == pytest.approx(weights[i])
            assert point["cumulative_weight"] == pytest.approx(math.fsum(weights[:i + 1]))
        quantile = lambda q: next(p["value"] for p in result["points"] if p["cumulative_weight"] >= q)
        assert result["median"] == quantile(0.5)
        assert result["quantiles"] == {"0.25": quantile(0.25), "0.75": quantile(0.75)}
        maximum = max(p["relative_weight"] for p in result["points"])
        assert result["mode"] == [p["value"] for p in result["points"] if p["relative_weight"] == maximum]
        if measurement == "interval":
            mean = math.fsum(p["value"] * p["relative_weight"] for p in result["points"])
            variance = math.fsum(p["relative_weight"] * (p["value"] - mean) ** 2 for p in result["points"])
            assert result["expected_value"] == pytest.approx(mean)
            assert result["standard_deviation"] == pytest.approx(math.sqrt(variance))
    after = decision_metrics()
    assert after["llamacpp:tokens_predicted_total"] == before["llamacpp:tokens_predicted_total"]
    assert after["llamacpp:spec_decode_num_draft_tokens_total"] == before["llamacpp:spec_decode_num_draft_tokens_total"]


def test_scale_invalid_and_recovery():
    server.n_slots = 1
    server.n_ctx = 128
    server.start()
    request = scale_request(["yes", "no"])
    invalid = [
        {"measurement": m} for m in [None, "Ordinal", "nominal", 1, True]
    ] + [
        {"scale": []}, {"scale": request["scale"][:1]}, {"scale": {}},
        {"scale": [{"value": 1, "label": "yes"}, {"value": 1.0, "label": "no"}]},
        {"scale": [{"value": 1, "label": "yes"}, {"value": 2, "label": "yes"}]},
        {"scale": [{"value": 1, "label": "yes", "extra": 0}, request["scale"][1]]},
        {"scale": [{"label": "yes"}, request["scale"][1]]},
        {"scale": [{"value": 1}, request["scale"][1]]},
        {"scale": [None, request["scale"][1]]},
        {"scale": [{"value": i, "label": str(i)} for i in range(257)]},
        {"scale": [{"value": 1, "label": "x" * (1024 * 1024 + 1)}, request["scale"][1]]},
        {"scale": [{"value": 1, "label": " yes" * 32769}, request["scale"][1]]},
        {"scale": [{"value": 1, "label": " yes" * 200}, request["scale"][1]]},
        {"messages": [{"role": "user", "content": "Hello"}]},
        {"prompt": ""}, {"prompt": None}, {"min": 1, "max": 5, "step": 1}, {"choices": ["yes", "no"]},
    ]
    for value in [None, True, "1", [], {}]:
        invalid.append({"scale": [{"value": value, "label": "yes"}, request["scale"][1]]})
    for label in [None, "", 1, []]:
        invalid.append({"scale": [{"value": 1, "label": label}, request["scale"][1]]})
    baseline = server.make_request("POST", "/scale", request)
    assert baseline.status_code == 200
    for patch in invalid:
        response = server.make_request("POST", "/scale", {**request, **patch})
        assert response.status_code == 400, patch
        recovered = server.make_request("POST", "/scale", request)
        assert recovered.status_code == 200
        assert recovered.body == baseline.body
    for literal in ["NaN", "Infinity", "-Infinity", "1e400"]:
        body = json.dumps(request).replace('"value": -1', '"value": ' + literal)
        response = requests.post(server.make_url("/scale"), data=body, headers={"Content-Type": "application/json"}, timeout=10)
        assert response.status_code == 400
    for missing in ["prompt", "measurement", "scale"]:
        response = server.make_request("POST", "/scale", {k: v for k, v in request.items() if k != missing})
        assert response.status_code == 400



@pytest.mark.parametrize("values", [
    [2.5, -1, 0], [9007199254740993, 9007199254740992.0, -1],
    [18446744073709551615, 18446744073709551616.0, -9223372036854775808],
    [-9223372036854775807, -9223372036854775808.0, 0],
    [18446744073709551615, 18446744073709551614, 18446744073709551616.0],
])
def test_scale_numeric_order(values):
    server.n_slots = 1
    server.start()
    request = scale_request(["yes", "no", " big dog"])
    for point, value in zip(request["scale"], values):
        point["value"] = value
    first = server.make_request("POST", "/scale", request)
    second = server.make_request("POST", "/scale", {**request, "scale": request["scale"][::-1]})
    assert first.status_code == second.status_code == 200
    assert [p["value"] for p in first.body["points"]] == sorted(values)
    assert first.body == second.body


def test_scale_token_collisions():
    server.start()
    short, long = decision_tokens("yes"), decision_tokens("yes indeed")
    assert len(short) < len(long) and long[:len(short)] == short
    for labels in [["yes", "yes indeed"], ["yes indeed", "yes"]]:
        response = server.make_request("POST", "/scale", scale_request(labels))
        assert response.status_code == 400
        assert "token-prefix" in response.body["error"]["message"]
    # SentencePiece escapes spaces to the same marker already present in the other label.
    assert decision_tokens(" yes") == decision_tokens("\u2581yes")
    response = server.make_request("POST", "/scale", scale_request([" yes", "\u2581yes"]))
    assert response.status_code == 400
    assert "distinct token sequences" in response.body["error"]["message"]

    short_label, long_label = " yes", "\u2581yes indeed"
    assert not long_label.startswith(short_label)
    short, long = decision_tokens(short_label), decision_tokens(long_label)
    assert len(short) < len(long) and long[:len(short)] == short
    response = server.make_request("POST", "/scale", scale_request([short_label, long_label]))
    assert response.status_code == 400
    assert "token-prefix" in response.body["error"]["message"]


@pytest.fixture(autouse=True)
def create_server():
    global server
    server = ServerPreset.tinyllama2()

@pytest.mark.parametrize("prompt,n_predict,re_content,n_prompt,n_predicted,truncated,return_tokens", [
    ("I believe the meaning of life is", 8, "(going|bed)+", 18, 8, False, False),
    ("Write a joke about AI from a very long prompt which will not be truncated", 64, "(princesses|everyone|kids|Anna|forest)+", 46, 64, False, True),
])
def test_completion(prompt: str, n_predict: int, re_content: str, n_prompt: int, n_predicted: int, truncated: bool, return_tokens: bool):
    global server
    server.start()
    res = server.make_request("POST", "/completion", data={
        "n_predict": n_predict,
        "prompt": prompt,
        "return_tokens": return_tokens,
    })
    assert res.status_code == 200
    assert res.body["timings"]["prompt_n"] == n_prompt
    assert res.body["timings"]["predicted_n"] == n_predicted
    assert res.body["truncated"] == truncated
    assert type(res.body["has_new_line"]) == bool
    assert match_regex(re_content, res.body["content"])
    if return_tokens:
        assert len(res.body["tokens"]) > 0
        assert all(type(tok) == int for tok in res.body["tokens"])
    else:
        assert res.body["tokens"] == []


@pytest.mark.parametrize("prompt,n_predict,re_content,n_prompt,n_predicted,truncated", [
    ("I believe the meaning of life is", 8, "(going|bed)+", 18, 8, False),
    ("Write a joke about AI from a very long prompt which will not be truncated", 64, "(princesses|everyone|kids|Anna|forest)+", 46, 64, False),
])
def test_completion_stream(prompt: str, n_predict: int, re_content: str, n_prompt: int, n_predicted: int, truncated: bool):
    global server
    server.start()
    res = server.make_stream_request("POST", "/completion", data={
        "n_predict": n_predict,
        "prompt": prompt,
        "stream": True,
    })
    content = ""
    for data in res:
        assert "stop" in data and type(data["stop"]) == bool
        if data["stop"]:
            assert data["timings"]["prompt_n"] == n_prompt
            assert data["timings"]["predicted_n"] == n_predicted
            assert data["truncated"] == truncated
            assert data["stop_type"] == "limit"
            assert type(data["has_new_line"]) == bool
            assert "generation_settings" in data
            assert server.n_predict is not None
            assert data["generation_settings"]["n_predict"] == min(n_predict, server.n_predict)
            assert data["generation_settings"]["seed"] == server.seed
            assert "adaptive_target" in data["generation_settings"]
            assert "adaptive_decay" in data["generation_settings"]
            assert match_regex(re_content, content)
        else:
            assert len(data["tokens"]) > 0
            assert all(type(tok) == int for tok in data["tokens"])
            content += data["content"]


def test_completion_stream_vs_non_stream():
    global server
    server.start()
    res_stream = server.make_stream_request("POST", "/completion", data={
        "n_predict": 8,
        "prompt": "I believe the meaning of life is",
        "stream": True,
    })
    res_non_stream = server.make_request("POST", "/completion", data={
        "n_predict": 8,
        "prompt": "I believe the meaning of life is",
    })
    content_stream = ""
    for data in res_stream:
        content_stream += data["content"]
    assert content_stream == res_non_stream.body["content"]


def test_completion_with_openai_library():
    global server
    server.start()
    client = OpenAI(api_key="dummy", base_url=f"http://{server.server_host}:{server.server_port}/v1")
    res = client.completions.create(
        model="davinci-002",
        prompt="I believe the meaning of life is",
        max_tokens=8,
    )
    assert res.system_fingerprint is not None and res.system_fingerprint.startswith("b")
    assert res.choices[0].finish_reason == "length"
    assert res.choices[0].text is not None
    assert match_regex("(going|bed)+", res.choices[0].text)


def test_completion_stream_with_openai_library():
    global server
    server.start()
    client = OpenAI(api_key="dummy", base_url=f"http://{server.server_host}:{server.server_port}/v1")
    res = client.completions.create(
        model="davinci-002",
        prompt="I believe the meaning of life is",
        max_tokens=8,
        stream=True,
    )
    output_text = ''
    for data in res:
        choice = data.choices[0]
        if choice.finish_reason is None:
            assert choice.text is not None
            output_text += choice.text
    assert match_regex("(going|bed)+", output_text)


# Test case from https://github.com/ggml-org/llama.cpp/issues/13780
@pytest.mark.slow
def test_completion_stream_with_openai_library_stops():
    global server
    server.model_hf_repo = "bartowski/Phi-3.5-mini-instruct-GGUF:Q4_K_M"
    server.model_hf_file = None
    server.start()
    client = OpenAI(api_key="dummy", base_url=f"http://{server.server_host}:{server.server_port}/v1")
    res = client.completions.create(
        model="davinci-002",
        prompt="System: You are helpful assistant.\nAssistant:\nHey! How could I help?\nUser:\nTell me a joke.\nAssistant:\n",
        stop=["User:\n", "Assistant:\n"],
        max_tokens=200,
        stream=True,
    )
    output_text = ''
    for data in res:
        choice = data.choices[0]
        if choice.finish_reason is None:
            assert choice.text is not None
            output_text += choice.text
    assert match_regex("Sure, here's one for[\\s\\S]*", output_text), f'Unexpected output: {output_text}'


@pytest.mark.parametrize("n_slots", [1, 2])
def test_consistent_result_same_seed(n_slots: int):
    global server
    server.n_slots = n_slots
    server.start()
    last_res = None
    for _ in range(4):
        res = server.make_request("POST", "/completion", data={
            "prompt": "I believe the meaning of life is",
            "seed": 42,
            "temperature": 0.0,
            "cache_prompt": False,  # TODO: remove this once test_cache_vs_nocache_prompt is fixed
        })
        if last_res is not None:
            assert res.body["content"] == last_res.body["content"]
        last_res = res


@pytest.mark.parametrize("n_slots", [1, 2])
def test_different_result_different_seed(n_slots: int):
    global server
    server.n_slots = n_slots
    server.start()
    last_res = None
    for seed in range(4):
        res = server.make_request("POST", "/completion", data={
            "prompt": "I believe the meaning of life is",
            "seed": seed,
            "temperature": 1.0,
            "cache_prompt": False,  # TODO: remove this once test_cache_vs_nocache_prompt is fixed
        })
        if last_res is not None:
            assert res.body["content"] != last_res.body["content"]
        last_res = res

# TODO figure why it don't work with temperature = 1
# @pytest.mark.parametrize("temperature", [0.0, 1.0])
@pytest.mark.parametrize("n_batch", [16, 32])
@pytest.mark.parametrize("temperature", [0.0])
def test_consistent_result_different_batch_size(n_batch: int, temperature: float):
    global server
    server.n_batch = n_batch
    server.start()
    last_res = None
    for _ in range(4):
        res = server.make_request("POST", "/completion", data={
            "prompt": "I believe the meaning of life is",
            "seed": 42,
            "temperature": temperature,
            "cache_prompt": False,  # TODO: remove this once test_cache_vs_nocache_prompt is fixed
        })
        if last_res is not None:
            assert res.body["content"] == last_res.body["content"]
        last_res = res


@pytest.mark.skip(reason="This test fails on linux, need to be fixed")
def test_cache_vs_nocache_prompt():
    global server
    server.start()
    res_cache = server.make_request("POST", "/completion", data={
        "prompt": "I believe the meaning of life is",
        "seed": 42,
        "temperature": 1.0,
        "cache_prompt": True,
    })
    res_no_cache = server.make_request("POST", "/completion", data={
        "prompt": "I believe the meaning of life is",
        "seed": 42,
        "temperature": 1.0,
        "cache_prompt": False,
    })
    assert res_cache.body["content"] == res_no_cache.body["content"]


def test_nocache_long_input_prompt():
    global server
    server.start()
    res = server.make_request("POST", "/completion", data={
        "prompt": "I believe the meaning of life is"*32,
        "seed": 42,
        "temperature": 1.0,
        "cache_prompt": False,
    })
    assert res.status_code == 400

def test_json_prompt_no_mtmd():
    global server
    server.start()
    res = server.make_request("POST", "/completion", data={
        "prompt": { JSON_PROMPT_STRING_KEY: "I believe the meaning of life is" },
        "seed": 42,
        "temperature": 1.0,
        "cache_prompt": False,
    })
    assert res.status_code == 200

def test_json_prompt_mtm_error_when_not_supported():
    global server
    server.start()
    res = server.make_request("POST", "/completion", data={
        "prompt": { JSON_PROMPT_STRING_KEY: "I believe the meaning of life is <__media__>", JSON_MULTIMODAL_KEY: "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=" },
        "seed": 42,
        "temperature": 1.0,
        "cache_prompt": False,
    })
    # MTMD is disabled on this model, so this should fail.
    assert res.status_code != 200

def test_completion_with_tokens_input():
    global server
    server.temperature = 0.0
    server.start()
    prompt_str = "I believe the meaning of life is"
    res = server.make_request("POST", "/tokenize", data={
        "content": prompt_str,
        "add_special": True,
    })
    assert res.status_code == 200
    tokens = res.body["tokens"]

    # single completion
    res = server.make_request("POST", "/completion", data={
        "prompt": tokens,
    })
    assert res.status_code == 200
    assert type(res.body["content"]) == str

    # batch completion
    res = server.make_request("POST", "/completion", data={
        "prompt": [tokens, tokens],
    })
    assert res.status_code == 200
    assert type(res.body) == list
    assert len(res.body) == 2
    assert res.body[0]["content"] == res.body[1]["content"]

    # mixed string and tokens
    res = server.make_request("POST", "/completion", data={
        "prompt": [tokens, prompt_str],
    })
    assert res.status_code == 200
    assert type(res.body) == list
    assert len(res.body) == 2
    assert res.body[0]["content"] == res.body[1]["content"]

    # mixed JSON and tokens
    res = server.make_request("POST", "/completion", data={
        "prompt": [
            tokens,
            {
                JSON_PROMPT_STRING_KEY: "I believe the meaning of life is",
            },
        ],
    })
    assert res.status_code == 200
    assert type(res.body) == list
    assert len(res.body) == 2
    assert res.body[0]["content"] == res.body[1]["content"]

    # mixed string and tokens in one sequence
    res = server.make_request("POST", "/completion", data={
        "prompt": [1, 2, 3, 4, 5, 6, prompt_str, 7, 8, 9, 10, prompt_str],
    })
    assert res.status_code == 200
    assert type(res.body["content"]) == str


@pytest.mark.parametrize("n_slots,n_requests", [
    (1, 3),
    (2, 2),
    (2, 4),
    (4, 2), # some slots must be idle
    (4, 6),
])
def test_completion_parallel_slots(n_slots: int, n_requests: int):
    global server
    server.n_slots = n_slots
    server.temperature = 0.0
    server.start()

    PROMPTS = [
        ("Write a very long book.", "(very|special|big)+"),
        ("Write another a poem.", "(small|house)+"),
        ("What is LLM?", "(Dad|said)+"),
        ("The sky is blue and I love it.", "(climb|leaf)+"),
        ("Write another very long music lyrics.", "(friends|step|sky)+"),
        ("Write a very long joke.", "(cat|Whiskers)+"),
    ]
    def check_slots_status():
        should_all_slots_busy = n_requests >= n_slots
        time.sleep(0.1)
        res = server.make_request("GET", "/slots")
        n_busy = sum([1 for slot in res.body if slot["is_processing"]])
        if should_all_slots_busy:
            assert n_busy == n_slots
        else:
            assert n_busy <= n_slots

    tasks = []
    for i in range(n_requests):
        prompt, re_content = PROMPTS[i % len(PROMPTS)]
        tasks.append((server.make_request, ("POST", "/completion", {
            "prompt": prompt,
            "seed": 42,
            "temperature": 1.0,
        })))
    tasks.append((check_slots_status, ()))
    results = parallel_function_calls(tasks)

    # check results
    for i in range(n_requests):
        prompt, re_content = PROMPTS[i % len(PROMPTS)]
        res = results[i]
        assert res.status_code == 200
        assert type(res.body["content"]) == str
        assert len(res.body["content"]) > 10
        # FIXME: the result is not deterministic when using other slot than slot 0
        # assert match_regex(re_content, res.body["content"])


@pytest.mark.parametrize(
    "n_ctx,n_slots,n_predict_vals,expected_success",
    [
        (256, 4, [80, 40, 80, 80], [True,  True,  True,  True]),
        (256, 4, [70, 70, 70, 70], [False, False, False, False]),
        (256, 4, [90, 90, 40, 90], [False, False, True,  False]),
        (256, 4, [90, 90, 40, 75], [True,  True,  True,  True]),
    ],
)
def test_completion_unified(n_ctx, n_slots, n_predict_vals, expected_success):
    global server
    server.n_slots = n_slots
    server.kv_unified = True
    server.n_ctx = n_ctx
    server.start()
    prompt = "A"
    tasks = []
    for n_predict in n_predict_vals:
        tasks.append((server.make_request, ("POST", "/completion", {"prompt": prompt, "n_predict": n_predict})))
    results = parallel_function_calls(tasks)
    for res, n_predict, expect_ok in zip(results, n_predict_vals, expected_success):
        if expect_ok:
            # the pool is aborted as a whole, so a request that fits on its own
            # is still dropped when the slots overlap, and it says so explicitly
            assert res.status_code == 200 or (
                res.status_code == 500
                and "context size has been exceeded" in res.body["error"]["message"].lower()
            )

        # note: https://github.com/ggml-org/llama.cpp/pull/18700#issuecomment-3728695581
        if res.status_code == 200:
            assert "content" in res.body
            if "timings" in res.body:
                assert res.body["timings"]["predicted_n"] == n_predict


@pytest.mark.parametrize(
    "prompt,n_predict,response_fields",
    [
        ("I believe the meaning of life is", 8, []),
        ("I believe the meaning of life is", 32, ["content", "generation_settings/n_predict", "prompt"]),
    ],
)
def test_completion_response_fields(
    prompt: str, n_predict: int, response_fields: list[str]
):
    global server
    server.start()
    res = server.make_request(
        "POST",
        "/completion",
        data={
            "n_predict": n_predict,
            "prompt": prompt,
            "response_fields": response_fields,
        },
    )
    assert res.status_code == 200
    assert "content" in res.body
    assert len(res.body["content"])
    if len(response_fields):
        assert res.body["generation_settings/n_predict"] == n_predict
        assert res.body["prompt"] == "<s> " + prompt
        assert isinstance(res.body["content"], str)
        assert len(res.body) == len(response_fields)
    else:
        assert len(res.body)
        assert "generation_settings" in res.body


def test_n_probs():
    global server
    server.start()
    res = server.make_request("POST", "/completion", data={
        "prompt": "I believe the meaning of life is",
        "n_probs": 10,
        "temperature": 0.0,
        "n_predict": 5,
    })
    assert res.status_code == 200
    assert "completion_probabilities" in res.body
    assert len(res.body["completion_probabilities"]) == 5
    for tok in res.body["completion_probabilities"]:
        assert "id" in tok and tok["id"] > 0
        assert "token" in tok and type(tok["token"]) == str
        assert "logprob" in tok and tok["logprob"] <= 0.0
        assert "bytes" in tok and type(tok["bytes"]) == list
        assert len(tok["top_logprobs"]) == 10
        for prob in tok["top_logprobs"]:
            assert "id" in prob and prob["id"] > 0
            assert "token" in prob and type(prob["token"]) == str
            assert "logprob" in prob and prob["logprob"] <= 0.0
            assert "bytes" in prob and type(prob["bytes"]) == list


def test_n_probs_stream():
    global server
    server.start()
    res = server.make_stream_request("POST", "/completion", data={
        "prompt": "I believe the meaning of life is",
        "n_probs": 10,
        "temperature": 0.0,
        "n_predict": 5,
        "stream": True,
    })
    for data in res:
        if data["stop"] == False:
            assert "completion_probabilities" in data
            assert len(data["completion_probabilities"]) == 1
            for tok in data["completion_probabilities"]:
                assert "id" in tok and tok["id"] > 0
                assert "token" in tok and type(tok["token"]) == str
                assert "logprob" in tok and tok["logprob"] <= 0.0
                assert "bytes" in tok and type(tok["bytes"]) == list
                assert len(tok["top_logprobs"]) == 10
                for prob in tok["top_logprobs"]:
                    assert "id" in prob and prob["id"] > 0
                    assert "token" in prob and type(prob["token"]) == str
                    assert "logprob" in prob and prob["logprob"] <= 0.0
                    assert "bytes" in prob and type(prob["bytes"]) == list


def test_n_probs_post_sampling():
    global server
    server.start()
    res = server.make_request("POST", "/completion", data={
        "prompt": "Today was the day. Today I would finally become a",
        "n_probs": 10,
        "temperature": 1.0,
        "n_predict": 5,
        "post_sampling_probs": True,
    })
    assert res.status_code == 200
    assert "completion_probabilities" in res.body
    assert len(res.body["completion_probabilities"]) == 5
    for (i, tok) in enumerate(res.body["completion_probabilities"]):
        assert "id" in tok and tok["id"] > 0
        assert "token" in tok and type(tok["token"]) == str
        assert "prob" in tok and 0.0 < tok["prob"] <= 1.0
        assert "bytes" in tok and type(tok["bytes"]) == list
        assert "top_probs" in tok and type(tok["top_probs"]) == list

        for prob in tok["top_probs"]:
            assert "id" in prob and prob["id"] > 0
            assert "token" in prob and type(prob["token"]) == str
            # 0.0 probability tokens should never be returned by the server
            assert "prob" in prob and 0.0 < prob["prob"] <= 1.0
            assert "bytes" in prob and type(prob["bytes"]) == list

        if i == 0:
            # The prompt is vague enough that we should get at least 10 possibilities
            # for the first token.
            assert len(tok["top_probs"]) == 10

        if len(tok["top_probs"]) < 10:
            # Getting less than the requested number of probabilities should only happen
            # if the ones we did get already sum to 1.0.
            assert sum(p["prob"] for p in tok["top_probs"]) == pytest.approx(1.0)

def test_n_probs_post_backend_sampling():
    """Verify that the same probabilities are returned with and without backend sampling."""
    global server
    server.backend_sampling = True
    server.start()

    def make_request(backend_sampling):
        n_predict = 20

        res = server.make_request("POST", "/completion", data={
            "prompt": "The countries of Europe, in random order, are:",
            "n_probs": 10,
            "n_predict": n_predict,
            "post_sampling_probs": True,
            "seed": 4242,
            "backend_sampling": backend_sampling,
        })
        assert res.status_code == 200

        total_probs = 0
        completions = res.body["completion_probabilities"]
        assert len(completions) == n_predict
        for tok in completions:
            # Handling of 0.0 probabilities differs between samplers and backend sampling. Filter them to normalize the
            # data.
            tok["top_probs"] = [x for x in tok["top_probs"] if x["prob"] > 0.0]
            total_probs += len(tok["top_probs"])
        # Verify that we got at least two top probs on average, to ensure the effectiveness of the test.
        assert total_probs >= 2 * n_predict
        return completions

    def verify_token(a, b):
        assert a["id"] == b["id"]
        assert a["token"] == b["token"]
        assert a["bytes"] == b["bytes"]
        assert a["prob"] == pytest.approx(b["prob"], abs=0.01)

    for (a, b) in zip(make_request(True), make_request(False)):
        verify_token(a, b)
        assert len(a["top_probs"]) == len(b["top_probs"])

        for (aa, bb) in zip(a["top_probs"], b["top_probs"]):
            verify_token(aa, bb)

@pytest.mark.parametrize("tokenize,openai_style", [(False, False), (False, True), (True, False), (True, True)])
def test_logit_bias(tokenize, openai_style):
    global server
    server.start()

    exclude = ["i", "I", "the", "The", "to", "a", "an", "be", "is", "was", "but", "But", "and", "And", "so", "So", "you", "You", "he", "He", "she", "She", "we", "We", "they", "They", "it", "It", "his", "His", "her", "Her", "book", "Book"]

    logit_bias = []
    if tokenize:
        res = server.make_request("POST", "/tokenize", data={
            "content": " " + " ".join(exclude) + " ",
        })
        assert res.status_code == 200
        tokens = res.body["tokens"]
        logit_bias = [[tok, -100] for tok in tokens]

    else:
        logit_bias = [[" " + tok + " ", -100] for tok in exclude]

    if openai_style:
        logit_bias = {el[0]: -100 for el in logit_bias}

    res = server.make_request("POST", "/completion", data={
        "n_predict": 64,
        "prompt": "What is the best book",
        "logit_bias": logit_bias,
        "temperature": 0.0
    })
    assert res.status_code == 200
    output_text = res.body["content"]
    assert all(output_text.find(" " + tok + " ") == -1 for tok in exclude)


def test_cancel_request():
    global server
    server.n_ctx = 4096
    server.n_predict = -1
    server.n_slots = 1
    server.server_slots = True
    server.start()
    # send a request that will take a long time, but cancel it before it finishes
    try:
        server.make_request("POST", "/completion", data={
            "prompt": "I believe the meaning of life is",
        }, timeout=0.1)
    except requests.exceptions.ReadTimeout:
        pass # expected
    # make sure the slot is free
    time.sleep(2)
    res = server.make_request("GET", "/slots")
    assert res.body[0]["is_processing"] == False


# this test exercises the host-memory prompt cache
# ref: https://github.com/ggml-org/llama.cpp/pull/16391
# ref: https://github.com/ggml-org/llama.cpp/pull/17078
def test_completion_prompt_cache():
    global server
    server.n_slots = 2
    server.kv_unified = True
    server.start()

    for _ in range(16):
        # generate alternating random prompts with variable lengths in order to get them in and out of the cache
        r = random.randint(0, 4)
        prompt = (" Hello " +  str(r)) * (40 + r)
        n_prompt = (40 + r)*5 + 2
        n_predict = random.randint(1, 8)

        res = server.make_request(
            "POST",
            "/completion",
            data={
                "prompt": prompt,
                "n_predict": n_predict,
            },
        )

        assert res.status_code == 200
        assert "content" in res.body
        content = res.body["content"]
        assert isinstance(content, str)
        assert len(content) > 0

        assert type(res.body["has_new_line"]) == bool
        assert "timings" in res.body
        timings = res.body["timings"]

        assert "prompt_n" in timings and timings["prompt_n"] + timings["cache_n"] == n_prompt
        assert "predicted_n" in timings and timings["predicted_n"] == n_predict
        assert "tokens" in res.body and isinstance(res.body["tokens"], list)

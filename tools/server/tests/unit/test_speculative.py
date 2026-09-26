import pytest
import requests
from pathlib import Path
from utils import *

# We use a F16 MOE gguf as main model, and q4_0 as draft model

server = ServerPreset.stories15m_moe()

MODEL_DRAFT_FILE_URL = "https://huggingface.co/ggml-org/tiny-llamas/resolve/main/stories15M-q4_0.gguf"

def create_server():
    global server
    server = ServerPreset.stories15m_moe()
    # set default values
    server.model_draft = download_file(MODEL_DRAFT_FILE_URL)
    server.spec_type = "draft-simple"
    server.spec_draft_n_min = 4
    server.spec_draft_n_max = 8
    server.fa = "off"


@pytest.fixture(autouse=True)
def fixture_create_server():
    return create_server()


def test_with_and_without_draft():
    global server
    request = {
        "prompt": "I believe the meaning of life is",
        "temperature": 0.2,
        "top_k": 5,
        "seed": 4242,
        "n_predict": 16,
        "return_tokens": True,
    }

    server.model_draft = None  # disable draft model
    server.spec_type = None
    server.start()
    res = server.make_request("POST", "/completion", data=request)
    assert res.status_code == 200
    tokens_no_draft = res.body["tokens"]
    server.stop()

    # create new server with draft model
    create_server()
    server.start()
    res = server.make_request("POST", "/completion", data=request)
    assert res.status_code == 200
    assert res.body["timings"]["draft_n"] > 0
    tokens_draft = res.body["tokens"]

    assert tokens_no_draft == tokens_draft

    server.stop()
    create_server()
    assert server.spec_draft_n_max is not None
    server.spec_synth_rates = [0.0] * server.spec_draft_n_max
    server.start()
    res = server.make_request("POST", "/completion", data=request)

    assert res.status_code == 200
    assert res.body["timings"]["draft_n"] > 0
    assert res.body["timings"]["draft_n_accepted"] == 0
    assert res.body["tokens"] == tokens_no_draft


def test_different_draft_min_draft_max():
    global server
    test_values = [
        (1, 2),
        (1, 4),
        (4, 8),
        (4, 12),
        (8, 16),
    ]
    last_content = None
    for draft_min, draft_max in test_values:
        server.stop()
        server.spec_draft_n_min = draft_min
        server.spec_draft_n_max = draft_max
        server.start()
        res = server.make_request("POST", "/completion", data={
            "prompt": "I believe the meaning of life is",
            "temperature": 0.0,
            "top_k": 1,
            "n_predict": 16,
        })
        assert res.status_code == 200
        if last_content is not None:
            assert last_content == res.body["content"]
        last_content = res.body["content"]


def test_synth_is_deterministic():
    global server
    assert server.spec_draft_n_max is not None
    server.spec_synth_rates = [0.75 ** (i + 1) for i in range(server.spec_draft_n_max)]
    server.start()

    request = {
        "prompt": "I believe the meaning of life is",
        "temperature": 0.2,
        "top_k": 5,
        "seed": 4242,
        "n_predict": 32,
    }
    responses = [server.make_request("POST", "/completion", data=request) for _ in range(2)]

    for res in responses:
        assert res.status_code == 200
        assert res.body["timings"]["draft_n"] > 0
    assert responses[0].body["timings"]["draft_n"] == responses[1].body["timings"]["draft_n"]
    assert responses[0].body["timings"]["draft_n_accepted"] == responses[1].body["timings"]["draft_n_accepted"]


def test_synth_ignores_target_tokens():
    global server
    assert server.spec_draft_n_max is not None
    server.spec_synth_rates = [1.0] * server.spec_draft_n_max
    server.start()

    res = server.make_request("POST", "/completion", data={
        "prompt": "I believe the meaning of life is",
        "temperature": 0.0,
        "seed": 4242,
        "n_predict": 32,
    })

    assert res.status_code == 200
    assert res.body["timings"]["draft_n"] > 0
    assert res.body["timings"]["draft_n_accepted"] == res.body["timings"]["draft_n"]

    res = server.make_request("POST", "/completion", data={
        "prompt": "I believe the meaning of life is",
        "temperature": 0.0,
        "seed": 4242,
        "n_predict": 6,
        "grammar": 'root ::= "a"{5,5}',
    })
    assert res.status_code == 200, res.body

    res = server.make_request("POST", "/completion", data={
        "prompt": "Respond with only: OK",
        "temperature": 0.0,
        "seed": 4242,
        "n_predict": 64,
        "ignore_eos": True,
    })
    assert res.status_code == 200, res.body
    assert res.body["tokens_predicted"] == 64
    assert res.body["stop_type"] == "limit"


def test_slot_ctx_not_exceeded():
    global server
    server.n_ctx = 256
    server.start()
    res = server.make_request("POST", "/completion", data={
        "prompt": "Hello " * 248,
        "temperature": 0.0,
        "top_k": 1,
        "speculative.p_min": 0.0,
    })
    assert res.status_code == 200
    assert len(res.body["content"]) > 0


def test_with_ctx_shift():
    global server
    server.n_ctx = 256
    server.enable_ctx_shift = True
    server.start()
    res = server.make_request("POST", "/completion", data={
        "prompt": "Hello " * 248,
        "temperature": 0.0,
        "top_k": 1,
        "n_predict": 256,
        "speculative.p_min": 0.0,
    })
    assert res.status_code == 200
    assert len(res.body["content"]) > 0
    assert res.body["tokens_predicted"] == 256
    assert res.body["truncated"] == True


@pytest.mark.parametrize("n_slots,n_requests", [
    (1, 2),
    (2, 2),
])
def test_multi_requests_parallel(n_slots: int, n_requests: int):
    global server
    server.n_slots = n_slots
    server.start()
    tasks = []
    for _ in range(n_requests):
        tasks.append((server.make_request, ("POST", "/completion", {
            "prompt": "I believe the meaning of life is",
            "temperature": 0.0,
            "top_k": 1,
        })))
    results = parallel_function_calls(tasks)
    for res in results:
        assert res.status_code == 200
        assert match_regex("(wise|kind|owl|answer)+", res.body["content"])


@pytest.mark.parametrize("multitoken_first", [False, True])
def test_mixed_decision_modes_with_draft(tmp_path, monkeypatch, multitoken_first):
    monkeypatch.setenv("LLAMA_BATCH_DEBUG", "1")
    server.n_slots = 2
    server.n_ctx = 4096
    server.n_batch = 32
    server.n_ubatch = 32
    server.server_slots = True
    server.server_continuous_batching = True
    server.debug = True
    server.log_path = str(tmp_path / "mixed-decision.log")
    server.start()

    prompt = "Once upon a time " * 256 + "Answer:"
    tokenized = server.make_request("POST", "/tokenize", {"content": prompt, "add_special": True, "parse_special": True})
    assert tokenized.status_code == 200
    if len(tokenized.body["tokens"]) % server.n_batch == 0:
        prompt += " yes"
        tokenized = server.make_request("POST", "/tokenize", {"content": prompt, "add_special": True, "parse_special": True})
        assert tokenized.status_code == 200
    # Leave room in the final prefill batch to expose mixing in either slot order.
    assert len(tokenized.body["tokens"]) % server.n_batch != 0
    requests_by_mode = {
        False: {"prompt": prompt, "choices": ["yes", "no"]},
        True: {"prompt": prompt, "choices": [" yes" * 128, " no" * 128]},
    }
    completion = {"prompt": prompt, "temperature": 0, "n_predict": 16, "return_tokens": True}
    baseline = server.make_request("POST", "/completion", {**completion, "cache_prompt": False})
    assert baseline.status_code == 200
    assert baseline.body["timings"]["draft_n"] > 0
    expected = {}
    for mode, request in requests_by_mode.items():
        response = server.make_request("POST", "/decision", request)
        assert response.status_code == 200
        expected[mode] = response.body["choices"]
    assert "token_id" in expected[False][0]
    assert "token_ids" in expected[True][0]

    # Restart so admission order is independent of the reference requests' cached prompts.
    server.stop()
    server.start()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(server.make_request, "POST", "/decision", requests_by_mode[multitoken_first])
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            slots = server.make_request("GET", "/slots")
            assert slots.status_code == 200
            active = [slot for slot in slots.body if slot["is_processing"]]
            if active:
                assert len(active) == 1
                first_slot = active[0]["id"]
                break
            assert not first.done(), "First decision finished before overlap could be established"
            time.sleep(0.001)
        else:
            pytest.fail("First decision was not admitted")

        second = pool.submit(server.make_request, "POST", "/decision", requests_by_mode[not multitoken_first])
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            slots = server.make_request("GET", "/slots")
            assert slots.status_code == 200
            active = [slot for slot in slots.body if slot["is_processing"]]
            if len(active) == 2:
                second_slot = next(slot["id"] for slot in active if slot["id"] != first_slot)
                break
            assert not first.done() and not second.done(), "Decision requests did not overlap"
            time.sleep(0.001)
        else:
            pytest.fail("Both decisions were not active concurrently")

        for mode, future in [(multitoken_first, first), (not multitoken_first, second)]:
            response = future.result(timeout=180)
            assert response.status_code == 200
            assert len(response.body["choices"]) == len(expected[mode])
            for actual, reference in zip(response.body["choices"], expected[mode]):
                assert actual["text"] == reference["text"]
                if mode:
                    assert actual["token_ids"] == reference["token_ids"]
                    assert actual["sum_log_probability"] == pytest.approx(reference["sum_log_probability"], abs=2e-4)
                    assert actual["mean_log_probability"] == pytest.approx(reference["mean_log_probability"], abs=2e-4)
                else:
                    assert actual["token_id"] == reference["token_id"]
                    assert actual["logit"] == pytest.approx(reference["logit"], abs=2e-4)
                    assert actual["probability"] == pytest.approx(reference["probability"], abs=2e-4)

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        trace = Path(server.log_path).read_text(encoding="utf-8", errors="replace")
        if trace.count("stop processing:") >= 2:
            break
        time.sleep(0.01)
    else:
        pytest.fail("Decision batch trace was not flushed")
    trace = trace[trace.index("processing task, is_child = 0"):]
    sequences = [set(map(int, ids.split())) for ids in re.findall(r"seq_id_unq\s*=\s*\[([\d ]+)\]", trace)]
    assert sequences, "LLAMA_BATCH_DEBUG did not record batch sequence IDs"
    assert set.union(*sequences) == {first_slot, second_slot}
    assert all(len(ids) == 1 for ids in sequences), "Legacy and multi-token decisions shared a batch"

    # Reuse the legacy prompt cache and also check the cleared multi-token slot.
    legacy_slot = second_slot if multitoken_first else first_slot
    multi_slot = first_slot if multitoken_first else second_slot
    for slot_id in [legacy_slot, multi_slot]:
        response = server.make_request("POST", "/completion", {**completion, "cache_prompt": True, "id_slot": slot_id})
        assert response.status_code == 200
        assert response.body["tokens"] == baseline.body["tokens"]
        assert response.body["timings"]["draft_n"] > 0
        if slot_id == legacy_slot:
            assert response.body["timings"]["cache_n"] > 0


@pytest.mark.parametrize("labels", [["yes", "no"], ["yes", " big dog", " little girl"]])
def test_scale_with_draft(labels):
    server.n_slots = 1
    server.server_metrics = True
    server.start()
    completion = {"prompt": "Once upon a time", "temperature": 0, "n_predict": 16, "cache_prompt": False}
    baseline = server.make_request("POST", "/completion", completion)
    assert baseline.status_code == 200
    assert baseline.body["timings"]["draft_n"] > 0

    def metrics():
        response = requests.get(server.make_url("/metrics"), timeout=10)
        assert response.status_code == 200
        return {line.split()[0]: float(line.split()[1]) for line in response.text.splitlines()
                if line.startswith("llamacpp:")}

    before = metrics()
    response = server.make_request("POST", "/scale", {
        "prompt": completion["prompt"], "measurement": "ordinal",
        "scale": [{"value": i, "label": label} for i, label in enumerate(labels)],
    })
    assert response.status_code == 200
    after = metrics()
    for key in ["llamacpp:tokens_predicted_total", "llamacpp:spec_decode_num_draft_tokens_total"]:
        assert before[key] == after[key]
    repeated = server.make_request("POST", "/completion", completion)
    assert repeated.status_code == 200
    assert repeated.body["content"] == baseline.body["content"]
    assert repeated.body["tokens_predicted"] == baseline.body["tokens_predicted"]

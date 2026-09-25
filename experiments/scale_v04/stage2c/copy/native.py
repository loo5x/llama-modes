"""Experimental ctypes bindings for the v0.3.0 Windows x64 headers only."""

import ctypes as C
import os
import hashlib
from pathlib import Path

P = C.c_void_p
I = C.c_int32
U = C.c_uint32
F = C.c_float
B = C.c_bool
S = C.c_size_t


class ModelParams(C.Structure):
    _fields_ = [("devices", P), ("tensor_buft_overrides", P), ("n_gpu_layers", I), ("split_mode", I),
                ("load_mode", I), ("lazy_mode", I), ("main_gpu", I), ("tensor_split", P),
                ("progress_callback", P), ("progress_callback_user_data", P), ("kv_overrides", P),
                *[(n, B) for n in ["vocab_only", "check_tensors", "use_extra_bufts", "no_host", "no_alloc", "load_mtp"]]]


class ContextParams(C.Structure):
    _fields_ = [*[(n, U) for n in ["n_ctx", "n_batch", "n_ubatch", "n_seq_max", "n_rs_seq", "n_outputs_max", "n_outputs_max_per_seq"]],
                *[(n, I) for n in ["n_threads", "n_threads_batch", "ctx_type", "rope_scaling_type", "pooling_type", "attention_type", "flash_attn_type"]],
                *[(n, F) for n in ["rope_freq_base", "rope_freq_scale", "yarn_ext_factor", "yarn_attn_factor", "yarn_beta_fast", "yarn_beta_slow"]],
                ("yarn_orig_ctx", U), ("defrag_thold", F), ("cb_eval", P), ("cb_eval_user_data", P),
                ("type_k", I), ("type_v", I), ("abort_callback", P), ("abort_callback_data", P),
                *[(n, B) for n in ["embeddings", "offload_kqv", "no_perf", "op_offload", "swa_full", "kv_unified"]],
                ("samplers", P), ("n_samplers", S), ("ctx_other", P)]


class Batch(C.Structure):
    _fields_ = [("n_tokens", I), ("token", C.POINTER(I)), ("embd", C.POINTER(F)), ("pos", C.POINTER(I)),
                ("n_seq_id", C.POINTER(I)), ("seq_id", C.POINTER(C.POINTER(I))), ("logits", C.POINTER(C.c_int8))]


class TensorHeader(C.Structure):
    _fields_ = [("type", I), ("buffer", P), ("ne", C.c_int64 * 4), ("nb", S * 4)]


EVAL = C.CFUNCTYPE(B, P, B, P)
LOG = C.CFUNCTYPE(None, I, C.c_char_p, P)


class Native:
    def __init__(self, runtime):
        if os.name != "nt" or C.sizeof(P) != 8:
            raise RuntimeError("This diagnostic requires native Windows x64")
        self.dll_directory = os.add_dll_directory(str(runtime))
        self.libs = [C.CDLL(str(runtime / name)) for name in ["ggml-base.dll", "ggml.dll", "llama.dll"]]
        self.bind("llama_version", C.c_char_p, [])
        if hashlib.sha256((runtime / "llama.dll").read_bytes()).hexdigest() != "41af4b14b2775d6c2005476d57aef8527fb18c5e58576e32e5ed29c9ed1bf7c5":
            raise RuntimeError("Bindings require the validated v0.3.0 DLL build")
        self.bind("ggml_backend_load_all_from_path", None, [C.c_char_p])
        self.bind("llama_backend_init", None, [])
        self.bind("llama_log_set", None, [LOG, P])
        self.bind("llama_model_default_params", ModelParams, [])
        self.bind("llama_context_default_params", ContextParams, [])
        self.bind("llama_model_load_from_file", P, [C.c_char_p, ModelParams])
        self.bind("llama_init_from_model", P, [P, ContextParams])
        self.bind("llama_model_free", None, [P])
        self.bind("llama_free", None, [P])
        self.bind("llama_get_memory", P, [P])
        self.bind("llama_memory_clear", None, [P, B])
        self.bind("llama_memory_seq_rm", B, [P, I, I, I])
        self.bind("llama_memory_seq_cp", None, [P, I, I, I, I])
        self.bind("llama_memory_seq_pos_min", I, [P, I])
        self.bind("llama_memory_seq_pos_max", I, [P, I])
        self.bind("llama_model_get_vocab", P, [P])
        self.bind("llama_vocab_n_tokens", I, [P])
        self.bind("llama_decode", I, [P, Batch])
        self.bind("llama_synchronize", None, [P])
        self.bind("llama_get_logits_ith", C.POINTER(F), [P, I])
        self.bind("llama_state_seq_get_size", S, [P, I])
        self.bind("llama_state_seq_get_data", S, [P, P, S, I])
        self.bind("llama_state_seq_set_data", S, [P, P, S, I])
        self.bind("llama_state_get_size", S, [P])
        self.bind("llama_state_get_data", S, [P, P, S])
        self.bind("llama_state_set_data", S, [P, P, S])
        self.bind("ggml_get_name", C.c_char_p, [P])
        self.bind("ggml_nbytes", S, [P])
        self.bind("ggml_backend_tensor_get", None, [P, P, S, S])
        self.ggml_backend_load_all_from_path(str(runtime).encode())
        self.llama_backend_init()

    def bind(self, name, result, arguments):
        for lib in self.libs:
            try:
                function = getattr(lib, name)
                function.restype, function.argtypes = result, arguments
                setattr(self, name, function)
                return
            except AttributeError:
                pass
        raise RuntimeError("Missing native function: " + name)

    def decode(self, context, tokens, position=0, sequence=0):
        n = len(tokens)
        tok = (I * n)(*tokens)
        pos = (I * n)(*range(position, position+n))
        counts = (I * n)(*([1] * n))
        seq = I(sequence)
        ids = (C.POINTER(I) * n)(*[C.pointer(seq) for _ in tokens])
        outputs = (C.c_int8 * n)(*([0]*(n-1) + [1]))
        batch = Batch(n, tok, None, pos, counts, ids, outputs)
        code = self.llama_decode(context, batch)
        if code != 0:
            raise RuntimeError(f"llama_decode failed: {code}")
        self.llama_synchronize(context)

    def snapshot(self, context, full=False, sequence=0):
        size = self.llama_state_get_size(context) if full else self.llama_state_seq_get_size(context, sequence)
        if not 0 < size < 1024**3:
            raise RuntimeError(f"Unexpected snapshot size: {size}")
        buffer = C.create_string_buffer(size)
        used = self.llama_state_get_data(context, buffer, size) if full else self.llama_state_seq_get_data(context, buffer, size, sequence)
        if used != size:
            raise RuntimeError("Snapshot size mismatch")
        return buffer

    def restore(self, context, buffer, full=False, sequence=0):
        size = C.sizeof(buffer)
        used = self.llama_state_set_data(context, buffer, size) if full else self.llama_state_seq_set_data(context, buffer, size, sequence)
        if used != size:
            raise RuntimeError("Restore size mismatch")
        self.llama_synchronize(context)

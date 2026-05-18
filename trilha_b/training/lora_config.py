from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)

MODEL_NAME = "Qwen/Qwen2.5-Coder-1.5B-Instruct"

LORA_TARGET_MODULES = [
    "q_proj",
    "v_proj",
    "k_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
]

# D-DEV-03: 6 GB, não 8 — o Qwen2.5-Coder-1.5B em fp16 (~3 GB peso +
# ativações com gradient_checkpointing) cabe em ~8 GB; ativar 4-bit aí
# degradaria a LoRA sem necessidade. Abaixo de 6 GB o 4-bit é justificado.
GPU_MEMORY_4BIT_THRESHOLD_GB = 6.0


@dataclass
class LoRATrainingConfig:
    rank: int = 16
    alpha: int = 32
    dropout: float = 0.05
    target_modules: list[str] = field(default_factory=lambda: list(LORA_TARGET_MODULES))
    bias: str = "none"
    task_type: str = "CAUSAL_LM"

    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 8
    gradient_checkpointing: bool = True

    learning_rate: float = 2e-4
    num_train_epochs: int = 3
    warmup_ratio: float = 0.03
    lr_scheduler_type: str = "cosine"
    weight_decay: float = 0.01
    max_grad_norm: float = 1.0

    fp16: bool = True
    bf16: bool = False

    logging_steps: int = 10
    save_steps: int = 100
    eval_steps: int = 100
    save_total_limit: int = 2
    load_best_model_at_end: bool = True
    metric_for_best_model: str = "eval_loss"
    greater_is_better: bool = False

    max_seq_length: int = 2048
    packing: bool = False


def _get_free_gpu_memory_gb() -> float:
    try:
        import torch
        if torch.cuda.is_available():
            free_bytes = torch.cuda.mem_get_info()[0]
            return free_bytes / (1024 ** 3)
    except Exception:
        pass
    return 0.0


def get_bnb_config():
    try:
        import bitsandbytes  # noqa: F401
        from transformers import BitsAndBytesConfig
        import torch
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
    except ImportError:
        logger.warning("bitsandbytes not available; 4-bit quantisation disabled")
        return None


def load_model_and_tokenizer(
    model_name_or_path: str = MODEL_NAME,
    use_4bit: Optional[bool] = None,
):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if use_4bit is None:
        free_gb = _get_free_gpu_memory_gb()
        use_4bit = 0 < free_gb < GPU_MEMORY_4BIT_THRESHOLD_GB
        logger.info("Free GPU memory: %.2f GB — 4-bit loading: %s", free_gb, use_4bit)

    tokenizer = AutoTokenizer.from_pretrained(model_name_or_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb_config = get_bnb_config() if use_4bit else None

    load_kwargs: dict = {
        "trust_remote_code": True,
        "device_map": "auto" if torch.cuda.is_available() else "cpu",
    }
    if bnb_config is not None:
        load_kwargs["quantization_config"] = bnb_config
    else:
        load_kwargs["torch_dtype"] = torch.float16 if torch.cuda.is_available() else torch.float32

    model = AutoModelForCausalLM.from_pretrained(model_name_or_path, **load_kwargs)

    if use_4bit and bnb_config is not None:
        try:
            from peft import prepare_model_for_kbit_training
            model = prepare_model_for_kbit_training(model)
        except ImportError:
            logger.warning("peft not available; skipping prepare_model_for_kbit_training")

    return model, tokenizer

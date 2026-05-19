"""
Smoke test: loads one R1 sample pair, runs a single CPU training step,
asserts loss > 0, and prints "Smoke test passed".

No GPU required. Uses the smallest possible config.
Run with: python scripts/smoke_test.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "training"))
sys.path.insert(0, str(ROOT / "data"))


def _load_sample_pair() -> dict:
    sample_file = ROOT / "data" / "sample_pairs" / "r1_long_method.json"
    pairs = json.loads(sample_file.read_text(encoding="utf-8"))
    return pairs[0]


def _run_one_step(pair: dict) -> float:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig, get_peft_model

    from instruction_templates import build_training_text
    from lora_config import LoRATrainingConfig, LORA_TARGET_MODULES

    MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"

    print(f"Loading tokenizer from {MODEL} ...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("Loading model on CPU (fp32, no quantisation) ...")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL,
        trust_remote_code=True,
        device_map="cpu",
        torch_dtype=torch.float32,
    )

    lora_cfg = LoraConfig(
        r=4,
        lora_alpha=8,
        lora_dropout=0.0,
        target_modules=["q_proj", "v_proj"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)
    model.train()

    # D-DEV-04: prompt via o chat template oficial do tokenizer.
    prompt = build_training_text(
        pair["smell_type"], pair["before_code"], pair["after_code"], tokenizer
    )

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=False,
    )
    input_ids = inputs["input_ids"]
    labels = input_ids.clone()

    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    optimizer.zero_grad()

    outputs = model(input_ids=input_ids, labels=labels)
    loss = outputs.loss
    loss_value = loss.item()

    loss.backward()
    optimizer.step()

    return loss_value


def main() -> None:
    pair = _load_sample_pair()
    print(f"Loaded sample pair: smell_type={pair['smell_type']}, function_name={pair.get('function_name')}")

    loss = _run_one_step(pair)
    print(f"Training step loss: {loss:.4f}")

    assert loss > 0, f"Expected loss > 0, got {loss}"
    print("Smoke test passed")


if __name__ == "__main__":
    main()

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fine-tune a LoRA adapter on Qwen2.5-Coder-1.5B for one code smell type."
    )
    parser.add_argument(
        "--smell_type",
        required=True,
        choices=["R1", "R2", "R3", "R4", "R5"],
        help="Code smell to target (R1=LongMethod, R2=LongParams, R3=MagicNumbers, "
             "R4=DeepNesting, R5=DeadCode)",
    )
    parser.add_argument(
        "--data_dir",
        required=True,
        type=Path,
        help="Path to a HuggingFace DatasetDict saved by data/curate.py",
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        type=Path,
        help="Directory where the trained adapter will be saved",
    )
    parser.add_argument(
        "--model_name_or_path",
        default="Qwen/Qwen2.5-Coder-1.5B-Instruct",
        help="HuggingFace model id or local path",
    )
    parser.add_argument(
        "--use_4bit",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Force 4-bit loading on/off. Auto-detected from free GPU memory by default.",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=None,
        help="Override number of training epochs from LoRATrainingConfig",
    )
    parser.add_argument(
        "--max_seq_length",
        type=int,
        default=None,
        help="Override maximum sequence length",
    )
    return parser.parse_args()


def _load_and_filter_dataset(data_dir: Path, smell_type: str):
    from datasets import load_from_disk

    dataset = load_from_disk(str(data_dir))
    logger.info("Loaded dataset splits: %s", list(dataset.keys()))
    filtered = dataset.filter(lambda ex: ex["smell_type"] == smell_type)
    for split, ds in filtered.items():
        logger.info("  %s: %d examples for %s", split, len(ds), smell_type)
    return filtered


def _build_formatting_func(smell_type: str, tokenizer):
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from instruction_templates import build_training_text

    def formatting_func(examples):
        # D-DEV-04: o chat template oficial do tokenizer renderiza a conversa
        # completa (system/user/assistant) e já fecha os turnos com <|im_end|> —
        # sem concatenar eos_token manualmente.
        texts = []
        for before, after in zip(examples["before_code"], examples["after_code"]):
            texts.append(build_training_text(smell_type, before, after, tokenizer))
        return texts

    return formatting_func


def main() -> None:
    args = _parse_args()

    adapter_output = args.output_dir / args.smell_type
    adapter_output.mkdir(parents=True, exist_ok=True)

    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from lora_config import LoRATrainingConfig, load_model_and_tokenizer

    cfg = LoRATrainingConfig()
    if args.epochs is not None:
        cfg.num_train_epochs = args.epochs
    if args.max_seq_length is not None:
        cfg.max_seq_length = args.max_seq_length

    logger.info("Loading model: %s", args.model_name_or_path)
    model, tokenizer = load_model_and_tokenizer(
        model_name_or_path=args.model_name_or_path,
        use_4bit=args.use_4bit,
    )

    from peft import LoraConfig, get_peft_model

    lora_cfg = LoraConfig(
        r=cfg.rank,
        lora_alpha=cfg.alpha,
        lora_dropout=cfg.dropout,
        target_modules=cfg.target_modules,
        bias=cfg.bias,
        task_type=cfg.task_type,
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    dataset = _load_and_filter_dataset(args.data_dir, args.smell_type)
    formatting_func = _build_formatting_func(args.smell_type, tokenizer)

    from transformers import TrainingArguments
    from trl import SFTTrainer

    training_args = TrainingArguments(
        output_dir=str(adapter_output),
        per_device_train_batch_size=cfg.per_device_train_batch_size,
        gradient_accumulation_steps=cfg.gradient_accumulation_steps,
        gradient_checkpointing=cfg.gradient_checkpointing,
        num_train_epochs=cfg.num_train_epochs,
        learning_rate=cfg.learning_rate,
        warmup_ratio=cfg.warmup_ratio,
        lr_scheduler_type=cfg.lr_scheduler_type,
        weight_decay=cfg.weight_decay,
        max_grad_norm=cfg.max_grad_norm,
        fp16=cfg.fp16,
        bf16=cfg.bf16,
        logging_steps=cfg.logging_steps,
        save_steps=cfg.save_steps,
        eval_steps=cfg.eval_steps if "validation" in dataset else None,
        eval_strategy="steps" if "validation" in dataset else "no",  # D-DEV-14
        save_total_limit=cfg.save_total_limit,
        load_best_model_at_end=cfg.load_best_model_at_end if "validation" in dataset else False,
        metric_for_best_model=cfg.metric_for_best_model,
        greater_is_better=cfg.greater_is_better,
        report_to="none",
    )

    train_dataset = dataset.get("train")
    eval_dataset = dataset.get("validation")

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        formatting_func=formatting_func,
        max_seq_length=cfg.max_seq_length,
        tokenizer=tokenizer,
        packing=cfg.packing,
    )

    logger.info("Starting training for smell_type=%s, epochs=%d", args.smell_type, cfg.num_train_epochs)
    train_result = trainer.train()
    logger.info("Training finished. Metrics: %s", train_result.metrics)

    trainer.model.save_pretrained(str(adapter_output))
    tokenizer.save_pretrained(str(adapter_output))
    logger.info("LoRA adapter saved to %s", adapter_output)


if __name__ == "__main__":
    main()

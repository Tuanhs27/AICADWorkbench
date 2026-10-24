# ==============================================================================
# Unsloth Fine-Tuning Script cho Dataset SFT (CadQuery Cleaned)
# Tương thích 100% với file cad_data_train_cleaned_vi.json / bilingual
# Chạy trên Google Colab GPU T4 (Bản Free 16GB VRAM)
# ==============================================================================

# Bước 1: Cài đặt Unsloth & thư viện tối ưu (Chạy lệnh shell trong Colab):
# !pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
# !pip install --no-deps trl peft accelerate bitsandbytes

from unsloth import FastLanguageModel
import torch
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments

# Bước 2: Cấu hình Base Model (Qwen2.5-Coder-3B hoặc 7B)
max_seq_length = 2048
load_in_4bit = True # Dùng QLoRA 4-bit để vừa vặn trong VRAM và train siêu nhanh

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Qwen2.5-Coder-3B-Instruct", # Hoặc "unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit"
    max_seq_length = max_seq_length,
    load_in_4bit = load_in_4bit,
)

# Bước 3: Cấu hình LoRA Adapters
model = FastLanguageModel.get_peft_model(
    model,
    r = 16, # LoRA Rank
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha = 16,
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = "unsloth",
    random_state = 3407,
)

# Bước 4: Nạp Dataset ChatML V2 Đa năng Cơ khí (cad_data_train_v2_mechanical.json)
# Tải file 'cad_data_train_v2_mechanical.json' lên thư mục làm việc của Colab
data_file = "cad_data_train_v2_mechanical.json" # Hoặc "cad_data_train_cleaned_vi.json"
dataset = load_dataset("json", data_files=data_file, split="train")

def formatting_prompts_func(examples):
    convos = examples["messages"]
    texts = [tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False) for convo in convos]
    return {"text": texts}

dataset = dataset.map(formatting_prompts_func, batched=True)

# Bước 5: Thiết lập Trainer
trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = max_seq_length,
    dataset_num_proc = 2,
    packing = False,
    args = TrainingArguments(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_steps = 10,
        max_steps = 120, # Hoặc num_train_epochs = 1
        learning_rate = 2e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        logging_steps = 5,
        optim = "adamw_8bit",
        weight_decay = 0.01,
        lr_scheduler_type = "linear",
        seed = 3407,
        output_dir = "outputs_cadquery",
    ),
)

# Chạy huấn luyện (~30 - 45 phút)
print("[*] Đang bắt đầu huấn luyện SFT...")
trainer.train()

# Bước 6: Xuất mô hình sang định dạng GGUF q4_k_m để nạp thẳng vào Ollama trên RTX 3050!
print("[*] Xuất mô hình sang GGUF (4-bit quantize)...")
model.save_pretrained_gguf("qwen2.5_coder_cadquery_sft", tokenizer, quantization_method = "q4_k_m")
print("[+] Hoàn tất! Tải file 'qwen2.5_coder_cadquery_sft-q4_k_m.gguf' về máy tính.")


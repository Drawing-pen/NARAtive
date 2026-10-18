import torch
import torch.nn as nn
from peft import LoraConfig, TaskType, get_peft_model
from transformers import AutoModel

MODEL_NAME = "xlm-roberta-base"
EMOTION_LABELS = ["sad", "angry", "fear", "happy"]
DIMENSION_CLASSES = {"profanity": 2, "sexual": 2, "violence": 2, "emotion": 4}


class MultiTaskRatingModel(nn.Module):
    def __init__(self, backbone, hidden_size, dimension_classes):
        super().__init__()
        self.backbone = backbone
        self.heads = nn.ModuleDict(
            {dim: nn.Linear(hidden_size, n) for dim, n in dimension_classes.items()}
        )

    def forward(self, encoded_inputs, dimension):
        outputs = self.backbone(**encoded_inputs)
        return self.heads[dimension](outputs.last_hidden_state[:, 0, :])


def build_model() -> MultiTaskRatingModel:
    backbone = AutoModel.from_pretrained(MODEL_NAME)
    lora_config = LoraConfig(
        task_type=TaskType.FEATURE_EXTRACTION,
        r=16,
        lora_alpha=32,
        lora_dropout=0.1,
        target_modules=["query", "key", "value"],
    )
    backbone = get_peft_model(backbone, lora_config)
    return MultiTaskRatingModel(backbone, backbone.config.hidden_size, DIMENSION_CLASSES)


def load_model(checkpoint_path: str, device: str = "cpu") -> MultiTaskRatingModel:
    model = build_model().to(device)
    checkpoint = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model
"""Analyzer konten: model XLM-RoBERTa + LoRA hasil latih (model_best.pt + tokenizer_xlmr)."""
import logging
import time
from pathlib import Path

from app.core.config import settings
from app.ml.lexicon import sexual_lexicon_score

log = logging.getLogger("uvicorn.error")

WINDOW_MAX_LENGTH = 256   # model dilatih di 128 token; jendela N-1/N/N+1 butuh lebih panjang
BATCH_SIZE = 16
EMOTION_LABELS = ["sad", "angry", "fear", "happy"]



class ModelAnalyzer:
    name = "xlmr-lora"

    def __init__(self, checkpoint: Path, tokenizer_dir: Path):
        import torch
        from transformers import AutoTokenizer

        from app.ml.model import load_model

        self.torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_dir))
        self.model = load_model(str(checkpoint), self.device)

    def _windows(self, paragraphs: list[str]) -> list[str]:
        """Sliding window N-1 / N / N+1 per paragraf."""
        out = []
        for i in range(len(paragraphs)):
            lo, hi = max(0, i - 1), min(len(paragraphs), i + 2)
            out.append(" ".join(paragraphs[lo:hi]))
        return out

    def analyze(self, paragraphs: list[str]) -> list[dict]:
        """Skor tiap paragraf. Hasil identik dengan memanggil model per dimensi, tapi lebih cepat:
        backbone dijalankan satu kali per batch (bukan 4 kali), lalu 4 kepala klasifikasi dipakai
        pada keluaran yang sama; teks diurutkan menurut panjang agar padding sedikit."""
        torch = self.torch
        texts = self._windows(paragraphs)
        n = len(texts)
        results = [dict() for _ in texts]
        order = sorted(range(n), key=lambda i: len(texts[i]))
        t0 = time.time()
        with torch.inference_mode():
            for start in range(0, n, BATCH_SIZE):
                idx = order[start:start + BATCH_SIZE]
                enc = self.tokenizer(
                    [texts[i] for i in idx], padding=True, truncation=True,
                    max_length=WINDOW_MAX_LENGTH, return_tensors="pt",
                ).to(self.device)
                cls = self.model.backbone(**enc).last_hidden_state[:, 0, :]
                heads = self.model.heads
                for dim in ("profanity", "sexual", "violence"):
                    probs = torch.softmax(heads[dim](cls), dim=1)[:, 1].cpu().tolist()
                    for j, v in zip(idx, probs):
                        results[j][dim] = round(v, 4)
                conf, emo = torch.softmax(heads["emotion"](cls), dim=1).max(dim=1)
                for j, e, c in zip(idx, emo.cpu().tolist(), conf.cpu().tolist()):
                    results[j]["emotion"] = EMOTION_LABELS[e]
                    results[j]["emotion_prob"] = round(c, 4)
                done = min(start + BATCH_SIZE, n)
                if (start // BATCH_SIZE) % 10 == 0 or done == n:
                    log.info("Analisis: %d/%d paragraf (%.0f detik)", done, n, time.time() - t0)
        # Sinyal kedua dimensi seksual: kamus kata eksplisit pada paragraf itu sendiri (bukan jendela 3 paragraf).
        for r, text in zip(results, paragraphs):
            r["sexual"] = max(r["sexual"], sexual_lexicon_score(text))
        return results


class ModelNotInstalled(RuntimeError):
    """File model belum ada di folder model/."""


def _model_paths() -> tuple[Path, Path]:
    model_dir = Path(settings.model_dir)
    return model_dir / "model_best.pt", model_dir / "tokenizer_xlmr"


def model_ready() -> bool:
    ckpt, tok = _model_paths()
    return ckpt.exists() and tok.exists()


_analyzer = None


def get_analyzer() -> ModelAnalyzer:
    global _analyzer
    if _analyzer is None:
        if not model_ready():
            ckpt, tok = _model_paths()
            raise ModelNotInstalled(f"Model tidak ditemukan. Taruh {ckpt.name} dan folder {tok.name} di {ckpt.parent.resolve()}.")
        ckpt, tok = _model_paths()
        _analyzer = ModelAnalyzer(ckpt, tok)
    return _analyzer


# Ambang skor per dimensi (paragraf dianggap "terdeteksi" bila skor >= ambang).
# Violence dinaikkan karena model terlalu sensitif di prosa naratif (dikalibrasi
# dari 4 buku Gutenberg: heuristik, bukan hasil validasi statistik).
THRESHOLDS = {"profanity": 0.5, "sexual": 0.5, "violence": 0.8}


ADULT_DIMENSIONS = ("sexual", "violence")   # dimensi yang menentukan rating dan persentase konten dewasa


def rate(pct: dict, counts: dict | None = None) -> str:
    """Aturan rating: persentase paragraf per dimensi DAN jumlah paragraf minimum.

    Jumlah minimum mencegah satu paragraf salah deteksi mengubah rating (pada naskah 20 paragraf,
    satu paragraf sudah 5%). Seksual cukup 2 paragraf karena satu adegan eksplisit pun bermakna.
    """
    # Bahasa kasar tidak dihitung: deteksinya masih sering keliru (terutama bahasa Indonesia) dan bukan penentu kedewasaan.
    sex, vio = pct["sexual"], pct["violence"]
    c = counts or {"sexual": 99, "violence": 99}
    if sex >= 3 and c["sexual"] >= 3:
        return "Explicit"
    if (vio >= 15 and c["violence"] >= 3) or (sex >= 1 and c["sexual"] >= 2):
        return "Mature"
    if (vio >= 3 and c["violence"] >= 2) or (sex >= 0.5 and c["sexual"] >= 2):
        return "Teen"
    return "General"


# Rentang usia pembaca yang disarankan per kategori rating (SRS FR-06).
AGE_RANGES = {"General": "Semua umur", "Teen": "13+", "Mature": "17+", "Explicit": "21+"}
NEGATIVE_EMOTIONS = ("sad", "angry", "fear")
EMOTION_MIN_CONF = 0.85


AI_WEIGHT = 0.7


def is_heavy(r: dict) -> bool:
    prob = r.get("emotion_prob")
    return r["emotion"] in NEGATIVE_EMOTIONS and prob is not None and prob >= EMOTION_MIN_CONF


def blend_heaviness(model_part: float | None, legacy: float, ai: float | None) -> float:
    if ai is None:
        return legacy if model_part is None else model_part
    if model_part is None:
        return ai
    return round(AI_WEIGHT * ai + (1 - AI_WEIGHT) * model_part, 1)


def summarize(results: list[dict], ai: float | None = None) -> dict:
    """Agregasi skor paragraf: persentase per dimensi, persentase konten dewasa, bobot cerita, rating, emosi dominan.

    - pct_adult  : % paragraf yang terdeteksi minimal satu dimensi dewasa, yaitu seksual atau kekerasan (gabungan, tanpa hitung ganda).
    - heaviness  : bobot cerita 0-100 = gabungan penilaian Gemini atas berat konflik dan tema (bobot 0,7) dengan % paragraf
                   bernada negatif yang diprediksi model dengan keyakinan tinggi (bobot 0,3).
    """
    n = max(len(results), 1)
    pct = {d: round(100 * sum(1 for r in results if r[d] >= t) / n, 1)
           for d, t in THRESHOLDS.items()}
    hit = {d: sum(1 for r in results if r[d] >= t) for d, t in THRESHOLDS.items()}
    adult = round(100 * sum(1 for r in results if any(r[d] >= THRESHOLDS[d] for d in ADULT_DIMENSIONS)) / n, 1)
    legacy = round(100 * sum(1 for r in results if r["emotion"] in NEGATIVE_EMOTIONS) / n, 1)
    model_part = round(100 * sum(1 for r in results if is_heavy(r)) / n, 1) if any(r.get("emotion_prob") is not None for r in results) else None
    heaviness = blend_heaviness(model_part, legacy, ai)
    counts = {}
    for r in results:
        counts[r["emotion"]] = counts.get(r["emotion"], 0) + 1
    dominant = max(counts, key=counts.get) if counts else None
    return {"pct": pct, "adult": adult, "heaviness": heaviness, "rating": rate(pct, hit), "emotion": dominant}
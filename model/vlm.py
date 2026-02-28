"""Vision-language model abstraction with auto-detected backend.

Supports two backends:
  - vllm : NVIDIA CUDA GPUs (Linux/Windows). Uses vllm.LLM.
  - mlx  : Apple Silicon (macOS M-series). Uses mlx-vlm.

Auto-detection order (--backend auto):
  1. NVIDIA GPU present → vllm
  2. Apple Silicon macOS → mlx
  3. Fallback            → vllm (CPU mode)

All backends expose the same three methods:
  describe_frame(base64_jpeg, prior_context) -> str
  answer_quiz(base64_jpeg, question, options, context) -> str
  compress_context(existing_summary, new_content) -> str

VLM calls are synchronous. Call from async code via asyncio.run_in_executor().
"""

from __future__ import annotations

import base64
import io
import platform

from model.prompts import (
    CONTEXT_COMPRESSION_PROMPT,
    FRAME_DESCRIPTION_PROMPT,
    FREE_TEXT_ANSWER_PROMPT,
    QUIZ_ANSWER_PROMPT,
)


# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------

def detect_backend() -> str:
    """Return 'vllm' or 'mlx' based on available hardware."""
    # NVIDIA GPU → vllm
    try:
        import torch
        if torch.cuda.is_available():
            print("[model] NVIDIA GPU detected → using vllm backend")
            return "vllm"
    except ImportError:
        pass

    # Apple Silicon → mlx
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        print("[model] Apple Silicon detected → using mlx backend")
        return "mlx"

    print("[model] No GPU detected → using vllm (CPU mode)")
    return "vllm"


# ---------------------------------------------------------------------------
# vLLM backend
# ---------------------------------------------------------------------------

class _VLLMBackend:
    def __init__(self, model_id: str, max_model_len: int, max_images: int) -> None:
        from vllm import LLM, SamplingParams

        print(f"[model/vllm] Loading {model_id}...")
        self._llm = LLM(
            model=model_id,
            max_model_len=max_model_len,
            limit_mm_per_prompt={"image": max_images},
        )
        self._params = SamplingParams(temperature=0.0, max_tokens=512)
        print("[model/vllm] Ready.")

    def _chat(self, messages: list) -> str:
        outputs = self._llm.chat(messages, self._params)
        return outputs[0].outputs[0].text.strip()

    def describe_frame(self, base64_jpeg: str, prior_context: str) -> str:
        prompt = FRAME_DESCRIPTION_PROMPT.format(context=prior_context or "None yet.")
        return self._chat([{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{base64_jpeg}"}},
                {"type": "text", "text": prompt},
            ],
        }])

    def answer_quiz(
        self, base64_jpeg: str, question: str, options: list[str], context: str
    ) -> str:
        options_text = "\n".join(f"{chr(65+i)}. {o}" for i, o in enumerate(options))
        prompt = QUIZ_ANSWER_PROMPT.format(
            context=context or "No course content captured yet.",
            question=question,
            options=options_text,
        )
        return self._chat([{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{base64_jpeg}"}},
                {"type": "text", "text": prompt},
            ],
        }])

    def answer_free_text(
        self, base64_jpeg: str, question: str, context: str
    ) -> str:
        prompt = FREE_TEXT_ANSWER_PROMPT.format(
            context=context or "No course content captured yet.",
            question=question,
        )
        return self._chat([{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{base64_jpeg}"}},
                {"type": "text", "text": prompt},
            ],
        }])

    def compress_context(self, existing_summary: str, new_content: str) -> str:
        prompt = CONTEXT_COMPRESSION_PROMPT.format(
            existing=existing_summary or "None yet.",
            new_content=new_content,
        )
        return self._chat([{
            "role": "user",
            "content": [{"type": "text", "text": prompt}],
        }])


# ---------------------------------------------------------------------------
# MLX backend  (Apple Silicon)
# ---------------------------------------------------------------------------

class _MLXBackend:
    def __init__(self, model_id: str) -> None:
        # transformers 4.50+ has two bugs when torchvision is absent:
        #   1. video_processor_class_from_name() crashes ("NoneType is not iterable")
        #      because VIDEO_PROCESSOR_MAPPING_NAMES stores None for torchvision-backed
        #      processors. Fix: skip None entries.
        #   2. AutoVideoProcessor.from_pretrained() raises ValueError("install torchvision")
        #      even for image-only use. Qwen2VLProcessor accepts video_processor=None, so
        #      returning None is safe.
        try:
            import importlib
            import transformers.models.auto.video_processing_auto as _vpa

            def _safe_video_processor_class_from_name(class_name: str):
                for module_name, extractors in _vpa.VIDEO_PROCESSOR_MAPPING_NAMES.items():
                    if not extractors:
                        continue
                    if class_name in extractors:
                        mod = importlib.import_module(
                            f".{module_name}", "transformers.models"
                        )
                        try:
                            return getattr(mod, class_name)
                        except AttributeError:
                            continue
                return None
            _vpa.video_processor_class_from_name = _safe_video_processor_class_from_name

            import transformers as _tf
            from transformers.utils.hub import PushToHubMixin as _PushToHubMixin
            _DummyBVP = _tf.BaseVideoProcessor  # dummy when torchvision absent

            # Stub that satisfies isinstance(stub, BaseVideoProcessor) AND
            # isinstance(stub, PushToHubMixin) so ProcessorMixin's to_dict()
            # serialises it correctly via stub.to_dict() → {}.
            class _VideoProcessorStub(_DummyBVP, _PushToHubMixin):
                def __init__(self):
                    pass  # skip requires_backends from DummyObject
                def to_dict(self):
                    return {}

            _orig_avp_from_pretrained = _vpa.AutoVideoProcessor.from_pretrained.__func__
            @classmethod  # type: ignore[misc]
            def _safe_avp_from_pretrained(cls, *args, **kwargs):
                try:
                    return _orig_avp_from_pretrained(cls, *args, **kwargs)
                except ValueError as exc:
                    if "torchvision" in str(exc):
                        # Return a no-op stub that passes type checks.
                        # Qwen2VL only uses the video processor for video inputs,
                        # which we never send.
                        return _VideoProcessorStub()
                    raise
            _vpa.AutoVideoProcessor.from_pretrained = _safe_avp_from_pretrained
        except Exception:
            pass  # transformers version that doesn't need the patch

        # mlx_lm unconditionally calls resource.setrlimit(RLIMIT_NOFILE, (2048, 4096))
        # at import time. On macOS the hard limit is often 2048, making that call
        # raise ValueError. Clamp the requested values to the current hard limit.
        import resource as _resource
        _orig_setrlimit = _resource.setrlimit
        def _safe_setrlimit(res, limits):
            if res == _resource.RLIMIT_NOFILE:
                _, cur_hard = _resource.getrlimit(_resource.RLIMIT_NOFILE)
                limits = (min(limits[0], cur_hard), min(limits[1], cur_hard))
            return _orig_setrlimit(res, limits)
        _resource.setrlimit = _safe_setrlimit
        try:
            from mlx_vlm import load
            from mlx_vlm.utils import load_config
        finally:
            _resource.setrlimit = _orig_setrlimit

        print(f"[model/mlx] Loading {model_id}...")
        self._model, self._processor = load(model_id)
        self._config = load_config(model_id)
        print("[model/mlx] Ready.")

    def _generate(self, prompt: str, image=None) -> str:
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template

        num_images = 1 if image is not None else 0
        formatted = apply_chat_template(
            self._processor, self._config, prompt, num_images=num_images
        )
        result = generate(
            self._model,
            self._processor,
            formatted,
            image,
            max_tokens=512,
            temp=0.0,
            verbose=False,
        )
        return result.text if hasattr(result, "text") else str(result)

    @staticmethod
    def _b64_to_pil(base64_jpeg: str):
        from PIL import Image
        data = base64.b64decode(base64_jpeg)
        return Image.open(io.BytesIO(data)).convert("RGB")

    def describe_frame(self, base64_jpeg: str, prior_context: str) -> str:
        prompt = FRAME_DESCRIPTION_PROMPT.format(context=prior_context or "None yet.")
        image = self._b64_to_pil(base64_jpeg)
        return self._generate(prompt, image)

    def answer_quiz(
        self, base64_jpeg: str, question: str, options: list[str], context: str
    ) -> str:
        options_text = "\n".join(f"{chr(65+i)}. {o}" for i, o in enumerate(options))
        prompt = QUIZ_ANSWER_PROMPT.format(
            context=context or "No course content captured yet.",
            question=question,
            options=options_text,
        )
        image = self._b64_to_pil(base64_jpeg)
        return self._generate(prompt, image)

    def answer_free_text(
        self, base64_jpeg: str, question: str, context: str
    ) -> str:
        prompt = FREE_TEXT_ANSWER_PROMPT.format(
            context=context or "No course content captured yet.",
            question=question,
        )
        image = self._b64_to_pil(base64_jpeg)
        return self._generate(prompt, image)

    def compress_context(self, existing_summary: str, new_content: str) -> str:
        prompt = CONTEXT_COMPRESSION_PROMPT.format(
            existing=existing_summary or "None yet.",
            new_content=new_content,
        )
        # Text-only: no image
        return self._generate(prompt, image=None)


# ---------------------------------------------------------------------------
# Public factory — the rest of the codebase only touches this
# ---------------------------------------------------------------------------

class VisionModel:
    """
    Singleton factory. Returns the appropriate backend for this machine.

    Usage:
        vlm = VisionModel.get(model_id=..., max_model_len=..., max_images=..., backend="auto")
        vlm.describe_frame(b64, ctx)
        vlm.answer_quiz(b64, question, options, ctx)
        vlm.compress_context(old_summary, new_content)
    """

    _instance: _VLLMBackend | _MLXBackend | None = None

    @classmethod
    def get(
        cls,
        model_id: str,
        max_model_len: int,
        max_images: int,
        backend: str = "auto",
    ) -> _VLLMBackend | _MLXBackend:
        if cls._instance is not None:
            return cls._instance

        resolved = backend if backend != "auto" else detect_backend()

        if resolved == "mlx":
            cls._instance = _MLXBackend(model_id)
        else:
            cls._instance = _VLLMBackend(model_id, max_model_len, max_images)

        return cls._instance

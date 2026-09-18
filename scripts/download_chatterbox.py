import inspect
import os
from pathlib import Path

from chatterbox.mtl_tts import ChatterboxMultilingualTTS

print("Downloading/loading Chatterbox multilingual model into the configured local model cache...")

loader = ChatterboxMultilingualTTS.from_pretrained
params = inspect.signature(loader).parameters
kwargs = {"device": "cpu"}
requested = os.getenv("CHATTERBOX_MULTILINGUAL_T3_MODEL", "v2")
if "t3_model" in params:
    kwargs["t3_model"] = requested
    print(f"Chatterbox API supports t3_model; caching multilingual {requested}.")
else:
    print("Installed Chatterbox API does not expose t3_model; using its default multilingual checkpoint.")

model = loader(**kwargs)
supported = getattr(model, "get_supported_languages", lambda: {})()
if supported and "pt" not in supported:
    raise RuntimeError("Installed Chatterbox multilingual model does not report Portuguese support.")

marker = Path(os.getenv("BRAMBLE_CHATTERBOX_READY", "runtime/chatterbox-model-ready.txt"))
marker.parent.mkdir(parents=True, exist_ok=True)
marker.write_text("ready\n", encoding="utf-8")
print("Chatterbox multilingual model is cached and ready for offline use.")

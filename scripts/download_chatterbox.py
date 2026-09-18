import os
import torch
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
print('Downloading/loading Chatterbox multilingual model into the configured local model cache...')
model=ChatterboxMultilingualTTS.from_pretrained(device='cpu',t3_model=os.getenv('CHATTERBOX_MULTILINGUAL_T3_MODEL','v2'))
print('Chatterbox model is ready for offline use.')

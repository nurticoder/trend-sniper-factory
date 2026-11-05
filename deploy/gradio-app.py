"""Free Gradio host entry point. Never download/install this runtime on the desktop."""
import os
import sys
from pathlib import Path

if not os.environ.get('SPACE_ID'):
    raise RuntimeError('This entry point runs only inside the connected Hugging Face Space')

source = str(Path(__file__).resolve().parent / 'src')
sys.path.insert(0, source)
os.environ['PYTHONPATH'] = source + os.pathsep + os.environ.get('PYTHONPATH', '')

root = '/tmp/trend-sniper-worker'
os.environ.update(
    TSF_WORKER_PROCESS='1', TSF_FREE_GRADIO='1', TSF_WORKER_DATA=root,
    TSF_VOICE_DATA=root + '/voice-model', OLLAMA_MODELS=root + '/ollama-models',
    OLLAMA_MAX_LOADED_MODELS='1', OLLAMA_NUM_PARALLEL='1',
    IMAGEIO_FFMPEG_EXE='/usr/bin/ffmpeg',
)

from trend_sniper.remote.worker import main

main()

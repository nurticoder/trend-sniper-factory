FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates zstd && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://ollama.com/install.sh | sh
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir '.[web,voice,worker]'
RUN trend-sniper install-voice --data-dir /opt/factory-voice
RUN useradd -m -u 1000 worker && mkdir -p /tmp/trend-sniper-worker /tmp/ollama && chown -R worker /tmp/trend-sniper-worker /tmp/ollama
ENV TSF_WORKER_PROCESS=1 TSF_WORKER_DATA=/tmp/trend-sniper-worker TSF_VOICE_DATA=/opt/factory-voice OLLAMA_MODELS=/tmp/ollama OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 IMAGEIO_FFMPEG_EXE=/usr/bin/ffmpeg PYTHONUNBUFFERED=1 PORT=7860
USER worker
EXPOSE 7860
CMD ["python", "-m", "trend_sniper.remote.worker"]

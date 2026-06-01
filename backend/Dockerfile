FROM python:3.11-slim

# ffmpeg нужен faster-whisper для декодирования mp3/wav/m4a и т.д.
# git нужен некоторым зависимостям pyannote при установке.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Ставим CPU-сборку torch И torchaudio отдельно, чтобы pyannote не подтянул
# CUDA-колёса torchaudio (они тащат libcudart и ломают импорт в CPU-контейнере).
# Версии torch/torchaudio обязаны совпадать.
RUN pip install --no-cache-dir torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Кэш моделей HuggingFace/Whisper — на volume, чтобы не качать при каждом старте.
ENV HF_HOME=/data/hf_cache
ENV UPLOAD_DIR=/data/uploads

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

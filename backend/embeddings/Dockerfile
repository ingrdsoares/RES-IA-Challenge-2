FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
# Torch só de CPU: o serviço roda em qualquer máquina com Docker, sem GPU.
RUN pip install --no-cache-dir torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt
COPY main.py .
ENV HF_HOME=/modelos
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

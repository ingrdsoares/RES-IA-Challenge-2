FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
ENV HF_HOME=/modelos
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

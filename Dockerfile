FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY configs/ ./configs/
RUN mkdir -p data
ENV DB_PATH=/app/data/prometheus.db
ENV GEMINI_MODEL=gemini-2.5-flash
ENV GEMINI_MODEL_NAME=gemini-2.5-flash
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

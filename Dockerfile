FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    MODEL_DIR=/app/artifacts \
    OMP_NUM_THREADS=1 \
    HOME=/tmp \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY streamlit_app.py .

# The model is trained at build time: an image tag identifies code and model together,
# and a model that misses the quality gate fails the build.
ARG GIT_SHA=dev
ENV MODEL_VERSION=$GIT_SHA
RUN python -m mlapp.train --output "$MODEL_DIR"

USER 10001
EXPOSE 8000 8501

# Serves the API by default. The UI runs the same image with a different command.
CMD ["uvicorn", "mlapp.api:app", "--host", "0.0.0.0", "--port", "8000"]

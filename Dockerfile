FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /work
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /work/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY pyproject.toml /work/pyproject.toml
COPY src /work/src
COPY configs /work/configs
COPY tests /work/tests
COPY run_full_study.py /work/run_full_study.py
COPY download_data.py /work/download_data.py
RUN pip install -e .
CMD ["python", "run_full_study.py", "--config", "configs/experiment.yaml"]

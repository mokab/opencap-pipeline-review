FROM stanfordnmbl/opensim-python:4.5

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential cmake git libopenblas-base curl \
    && rm -rf /var/lib/apt/lists/*

# Python packages compatible with Python 3.8
RUN pip install --no-cache-dir \
    numpy==1.24.4 \
    scipy==1.10.0 \
    casadi==3.7.2 \
    pandas==2.0.3 \
    matplotlib==3.7.5 \
    pyyaml \
    joblib==1.4.2 \
    seaborn \
    requests \
    ipython \
    python-decouple \
    maskpass==0.3.6 \
    cmake

# Clone opencap-processing at the commit used for the results (see git_hashes.yaml)
RUN git clone https://github.com/stanfordnmbl/opencap-processing.git /app/opencap-processing \
    && cd /app/opencap-processing && git checkout 72b5416bf6172fe3d9b42b01e1a02252362b20fc

# Create dummy .env to prevent API_TOKEN import failure
RUN echo "API_TOKEN=dummy" > /app/opencap-processing/.env

WORKDIR /app/opencap-processing

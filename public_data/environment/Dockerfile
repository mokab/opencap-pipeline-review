# 公開データ再分析ノートブック（public_data/*.ipynb）と実行例の評価・作図ノートブック
# （execution_example/reproduce_example.ipynb）を実行するための環境。
# OpenSimAD の最適化そのものは execution_example/environment/Dockerfile を使う。
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

WORKDIR /work
EXPOSE 8888
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", "--ServerApp.token=", "--ServerApp.password="]

FROM mambaorg/micromamba:2.3.3
COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml /tmp/environment.yml
RUN micromamba install -y -n base -f /tmp/environment.yml && micromamba clean --all --yes
WORKDIR /app
COPY --chown=$MAMBA_USER:$MAMBA_USER online /app/online
COPY --chown=$MAMBA_USER:$MAMBA_USER diagnostics /app/diagnostics
COPY --chown=$MAMBA_USER:$MAMBA_USER build/nbs_prepare /app/nbs_prepare
ENV PYTHONUNBUFFERED=1 NBS_DATA_DIR=/data
CMD ["python", "-m", "uvicorn", "online.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]

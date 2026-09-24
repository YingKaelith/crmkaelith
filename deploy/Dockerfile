# Receita fornecida para homologação; não executada no ambiente desta entrega.
FROM python:3.13-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 NEXO_DATA_DIR=/var/lib/nexo
WORKDIR /app
COPY requirements.txt requirements-postgres.txt ./
RUN pip install --no-cache-dir -r requirements-postgres.txt \
 && useradd --uid 10001 --create-home nexo \
 && mkdir -p /var/lib/nexo && chown 10001:10001 /var/lib/nexo
COPY --chown=10001:10001 server/ ./server/
COPY --chown=10001:10001 web/ ./web/
USER 10001:10001
EXPOSE 8000
CMD ["python","-m","server.run"]

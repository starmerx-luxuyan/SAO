FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN python -m pip install --no-cache-dir .

EXPOSE 8080

CMD ["python", "-m", "sao_mcp"]

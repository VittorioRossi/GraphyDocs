FROM python:3.11-slim

WORKDIR /app

# Install git
RUN apt-get update && apt-get install -y git

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    python3-dev \
    libpq-dev \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Install clangd
RUN apt-get install -y clangd


COPY lsp_installer.sh .
RUN chmod +x lsp_installer.sh
RUN ./lsp_installer.sh

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-exclude", "projects/*"]
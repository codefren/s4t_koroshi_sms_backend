FROM python:3.11-slim

# Install system dependencies and ODBC driver
RUN apt-get update && apt-get install -y \
    curl \
    gnupg2 \
    unixodbc \
    unixodbc-dev \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && apt-get clean

WORKDIR /app

# Install python dependencies
COPY pyproject.toml .
RUN pip install .

# Copy application code
COPY src/ src/
COPY scripts/ scripts/
COPY 1111087088_last.csv .

# Command to run the app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--reload"]

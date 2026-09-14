FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps . && useradd --create-home appuser && mkdir /data && chown appuser /data
USER appuser
ENV TRIPLEDGER_DATA_DIR=/data
EXPOSE 8000
CMD ["python", "-m", "expense_ai_copilot", "--host", "0.0.0.0"]

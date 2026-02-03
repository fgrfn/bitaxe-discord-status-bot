FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Create data and logs directories
RUN mkdir -p /app/data /app/logs

# Environment variables (can be overridden)
ENV DISCORD_BOT_TOKEN=""
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "-m", "src.main"]

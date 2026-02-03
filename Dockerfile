FROM python:3.14-slim

WORKDIR /app

# Install build dependencies for compiling Python packages (needed for discord.py's audioop-lts on ARM)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Remove build dependencies to keep image small
RUN apt-get purge -y --auto-remove gcc

# Copy source code
COPY src/ ./src/

# Create data and logs directories
RUN mkdir -p /app/data /app/logs

# Environment variables (can be overridden)
ENV DISCORD_BOT_TOKEN=""
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "-m", "src.main"]

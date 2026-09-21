FROM python:3.11-slim

WORKDIR /app

# Copy web requirements and install
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

# Copy web bridge file
COPY web_bridge.py .

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV PORT=10000

EXPOSE 10000

# Start Web Gateway Bridge (NOT the Discord Bot)
CMD ["python", "web_bridge.py"]

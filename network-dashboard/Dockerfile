FROM python:3.12-alpine

# ping for latency checks and the LAN sweep; tzdata for local times.
RUN apk add --no-cache iputils tzdata

COPY server.py /app/
COPY static /app/static

# Home Assistant mounts the add-on's persistent storage at /data.
ENV DASH_DATA_DIR=/data
CMD ["python3", "/app/server.py", "--port", "8081"]

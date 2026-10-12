FROM python:3.12-alpine

# Time zone data, so the daily reset follows the TZ that Home Assistant passes in.
RUN apk add --no-cache tzdata

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY server.py agenda.py display.py ha.py config.example.json /app/
COPY static /app/static

# Home Assistant mounts the add-on's persistent storage at /data,
# so kids, chores and check-offs survive restarts and updates.
ENV CHORE_DATA_DIR=/data
EXPOSE 8080
CMD ["python3", "/app/server.py", "--port", "8080"]

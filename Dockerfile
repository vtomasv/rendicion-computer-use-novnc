FROM node:22-bookworm-slim AS ui
WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 DISPLAY=:99 XDG_SESSION_TYPE=x11 PORT=8080 DEMO_DATA=/workspace/data XDG_RUNTIME_DIR=/tmp/runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb x11vnc openbox websockify novnc chromium libreoffice-calc \
    tesseract-ocr tesseract-ocr-spa xclip xdotool scrot poppler-utils \
    fonts-dejavu-core python3-tk ca-certificates libx11-6 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . ./
COPY --from=ui /src/frontend/dist/ ./frontend/dist/
RUN cp docker/start.sh /usr/local/bin/start-demo && chmod +x /usr/local/bin/start-demo \
    && useradd -m -u 10001 demo \
    && mkdir -p /workspace/data /tmp/runtime /tmp/.X11-unix \
    && chmod 1777 /tmp/.X11-unix && chown -R demo:demo /workspace /tmp/runtime
USER demo
EXPOSE 8080 6080
CMD ["/usr/local/bin/start-demo"]

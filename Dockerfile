FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/yarn.lock ./
RUN corepack enable && yarn install --frozen-lockfile

COPY frontend ./ 
ENV NEXT_TELEMETRY_DISABLED=1
RUN yarn build


FROM node:20-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    ffmpeg \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

RUN pip3 install --no-cache-dir --break-system-packages \
    "pyJianYingDraft @ git+https://github.com/linyqh/pyJianYingDraft.git" \
    || echo "pyJianYingDraft install failed, EDL fallback will be used"

COPY . .

COPY --from=frontend-builder /app/frontend/.next /app/frontend/.next
COPY --from=frontend-builder /app/frontend/node_modules /app/frontend/node_modules
COPY --from=frontend-builder /app/frontend/package.json /app/frontend/package.json

RUN chmod +x /app/docker/start.sh

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT_FRONTEND=3000 \
    PORT_API=8000

EXPOSE 3000 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://127.0.0.1:3000 || exit 1

CMD ["/app/docker/start.sh"]


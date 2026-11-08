# syntax=docker/dockerfile:1.7
#
# Dockerfile cho Web Frontend và Nginx reverse proxy (BE-16).
# Build từ gốc repo:
#   docker build -f infra/docker/web.Dockerfile -t meeting-web .
#
FROM node:24-bookworm-slim AS builder

WORKDIR /app/frontend

# Cài đặt dependency theo layer để tối ưu cache (dùng --legacy-peer-deps cho tương thích React 19)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps

# Copy toàn bộ mã nguồn frontend
COPY frontend/ ./
# FE-19 đọc capability từ contract khi Vite nạp cấu hình.
COPY contracts/openapi.json /app/contracts/openapi.json

# Build giao diện frontend tĩnh
RUN npx vite build

FROM nginx:1.27-alpine

# Copy tệp cấu hình Nginx bảo mật (chặn /metrics, proxy /api và /health)
COPY infra/docker/nginx.conf /etc/nginx/conf.d/default.conf

# Copy bản build frontend vào thư mục phục vụ web của Nginx
COPY --from=builder /app/frontend/dist /usr/share/nginx/html

# Cấu hình quyền cho user nginx (non-root) và chuyển PID sang /tmp/nginx.pid
RUN sed -i 's,^pid[[:space:]].*;,pid /tmp/nginx.pid;,' /etc/nginx/nginx.conf \
    && touch /tmp/nginx.pid \
    && chown -R nginx:nginx /tmp/nginx.pid /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx

USER nginx

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]

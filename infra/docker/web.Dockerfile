# syntax=docker/dockerfile:1.7
#
# Dockerfile cho Web Frontend và Nginx reverse proxy (BE-16).
# Build từ gốc repo:
#   docker build -f infra/docker/web.Dockerfile -t meeting-web .
#
FROM node:20-bookworm-slim AS builder

WORKDIR /app

# Cài đặt dependency theo layer để tối ưu cache
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy toàn bộ mã nguồn frontend
COPY frontend/ ./

# Build giao diện frontend tĩnh
RUN npm run build || npx vite build

FROM nginx:1.27-alpine

# Copy tệp cấu hình Nginx bảo mật (chặn /metrics, proxy /api và /health)
COPY infra/docker/nginx.conf /etc/nginx/conf.d/default.conf

# Copy bản build frontend vào thư mục phục vụ web của Nginx
COPY --from=builder /app/dist /usr/share/nginx/html

# Cấu hình quyền cho user nginx (non-root) và chuyển PID sang /tmp/nginx.pid
RUN sed -i 's,/var/run/nginx.pid,/tmp/nginx.pid,g' /etc/nginx/nginx.conf \
    && touch /tmp/nginx.pid \
    && chown -R nginx:nginx /tmp/nginx.pid /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx

USER nginx

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]

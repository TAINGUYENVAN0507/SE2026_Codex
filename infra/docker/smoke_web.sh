#!/bin/sh
# FE-19/BE-16: kiểm image đã build khởi động được dưới user mặc định.
set -eu

image="${1:-meeting-web:latest}"
container="meeting-web-smoke-$$"
cleanup() {
    result=$?
    trap - EXIT HUP INT TERM
    if [ "$result" -ne 0 ]; then
        docker logs "$container" 2>/dev/null || true
    fi
    docker rm --force "$container" >/dev/null 2>&1 || true
    exit "$result"
}
trap cleanup EXIT HUP INT TERM

# Không override user: phải kiểm đúng cấu hình non-root của image phát hành.
user=$(docker image inspect "$image" --format '{{.Config.User}}')
case "$user" in
    ''|0|root|0:*|root:*) echo 'Web image phải chạy dưới user non-root.' >&2; exit 1 ;;
esac
docker run --rm --add-host api:127.0.0.1 "$image" nginx -t

docker run --detach --rm --name "$container"     --add-host api:127.0.0.1 --publish 127.0.0.1::8080 "$image" >/dev/null
port=$(docker port "$container" 8080/tcp | sed 's/.*://')
[ -n "$port" ] || { echo 'Không tìm thấy cổng Web container.' >&2; exit 1; }
base="http://127.0.0.1:$port"
for path in / /settings; do
    count=0
    code=000
    while [ "$count" -lt 15 ]; do
        code=$(curl --silent --max-time 3 --output /dev/null --write-out '%{http_code}' "$base$path" || true)
        [ "$code" = 200 ] && break
        count=$((count + 1))
        sleep 1
    done
    [ "$code" = 200 ] || { echo "Web smoke $path: cần HTTP 200, nhận $code." >&2; exit 1; }
    echo "Web smoke $path: HTTP 200."
done
code=$(curl --silent --max-time 3 --output /dev/null --write-out '%{http_code}' "$base/metrics")
[ "$code" = 404 ] || { echo 'Web proxy phải chặn /metrics bằng HTTP 404.' >&2; exit 1; }
echo 'Web smoke /metrics: HTTP 404; Nginx non-root đạt.'

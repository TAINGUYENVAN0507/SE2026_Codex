#!/bin/sh
# FE-19/BE-16: kiểm image đã build khởi động được dưới user mặc định.
set -eu

image="${1:-meeting-web:latest}"
container="meeting-web-smoke-$$"
cleanup() {
    result=$?
    trap - EXIT HUP INT TERM
    if [ "$result" -ne 0 ]; then
        docker logs "$container" 2>&1 || true
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


# AD-018: cả đường SPA và API phải giữ query/referer khỏi log container.
canary="CANARY_WEB_QUERY_$(date +%s)_$$"
for path in "/?q=$canary" "/api/v1/meetings?q=$canary"; do
    code=$(curl --silent --max-time 5 --referer "http://example.invalid/?q=$canary" \
        --output /dev/null --write-out '%{http_code}' "$base$path")
    case "$code" in
        200|502) ;;
        *) echo "Web privacy smoke: nhận HTTP $code không mong đợi." >&2; exit 1 ;;
    esac
done
# Đợi bộ lọc ghi chẩn đoán upstream ra stderr; kiểm logging vẫn hoạt động.
count=0
while :; do
    logs=$(docker logs "$container" 2>&1)
    printf '%s' "$logs" | grep -Fq 'connect() failed' && break
    count=$((count + 1))
    [ "$count" -lt 5 ] || { echo 'Thiếu chẩn đoán upstream trong error log.' >&2; exit 1; }
    sleep 1
done
if printf '%s' "$logs" | grep -Fq "$canary"; then
    echo 'Web privacy smoke: query/referer canary bị ghi vào log container.' >&2
    exit 1
fi
echo 'Web privacy smoke: query string và referer không xuất hiện trong log container.'

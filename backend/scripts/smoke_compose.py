#!/usr/bin/env python3
"""Smoke test end-to-end trên cụm Docker Compose (BE-16, BE-15).

Quy trình kiểm thử:
1. Chờ API service sẵn sàng (health check HTTP 200).
2. Tạo tài khoản người dùng tổng hợp.
3. Đăng nhập qua POST /api/v1/auth/login và nhận session cookie.
4. Tải lên tệp âm thanh WAV tổng hợp qua POST /api/v1/meetings.
5. Poll trạng thái job qua GET /api/v1/jobs/{job_id} cho đến khi succeeded.
6. Tải bản xuất cuộc họp qua GET /api/v1/meetings/{meeting_id}/export.
7. Xóa cuộc họp (DELETE /api/v1/meetings/{id}) và xóa tài khoản (DELETE /api/v1/auth/me).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import subprocess
import sys
import time
import uuid
import wave

import httpx


def make_wav_bytes(seconds: int = 2) -> bytes:
    """Tạo buffer nhị phân file WAV im lặng cho kiểm thử khói."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000 * seconds)
    return buf.getvalue()


def wait_for_api(base_url: str, timeout_sec: int = 60) -> None:
    """Chờ endpoint /api/v1/health sẵn sàng."""
    print(f"1. Đang chờ API sẵn sàng tại {base_url}/api/v1/health (tối đa {timeout_sec}s)...")
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{base_url}/api/v1/health", timeout=3.0)
            if resp.status_code == 200:
                print("   -> API đã sẵn sàng (HTTP 200).")
                return
        except httpx.HTTPError:
            pass
        time.sleep(1.0)
    raise TimeoutError(f"API không phản hồi sau {timeout_sec} giây.")


def create_synthetic_user(email: str, name: str, password: str) -> None:
    """Tạo người dùng tổng hợp qua docker compose exec hoặc session DB trực tiếp."""
    print(f"2. Tạo tài khoản tổng hợp: {email}...")
    code = (
        f"from app.scripts.create_user import create_user; "
        f"from app.db.session import get_session_factory; "
        f"s = get_session_factory()(); "
        f"create_user(s, '{email}', '{name}', '{password}'); "
        f"s.close()"
    )
    # Thử qua docker compose exec trước (cho Compose stack)
    cmd = ["docker", "compose", "exec", "-T", "api", "python", "-c", code]
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if proc.returncode == 0:
            print("   -> Đã tạo user qua docker compose exec api.")
            return
    except Exception:
        pass

    # Fallback: chạy trực tiếp trong môi trường local nếu có kết nối DB
    try:
        from app.db.session import get_session_factory
        from app.scripts.create_user import create_user

        session = get_session_factory()()
        create_user(session, email, name, password)
        session.close()
        print("   -> Đã tạo user qua local database session.")
    except Exception as exc:
        raise RuntimeError(f"Không thể tạo user tổng hợp: {exc}") from exc


def run_smoke(base_url: str, timeout_sec: int = 60) -> None:
    """Chạy toàn bộ luồng smoke test."""
    wait_for_api(base_url, timeout_sec=timeout_sec)

    uid = uuid.uuid4().hex[:8]
    email = f"smoke_{uid}@example.local"
    name = f"Smoke User {uid}"
    password = f"SmokePass!{uid}A1"

    create_synthetic_user(email, name, password)

    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        # 3. Đăng nhập
        print("3. Đăng nhập qua POST /api/v1/auth/login...")
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        if login_res.status_code != 200:
            raise RuntimeError(f"Đăng nhập thất bại ({login_res.status_code}): {login_res.text}")
        print("   -> Đăng nhập thành công, nhận session cookie.")

        # 4. Upload file WAV tổng hợp
        print("4. Tải lên tệp âm thanh WAV tổng hợp...")
        wav_data = make_wav_bytes(2)
        files = {"file": ("smoke.wav", wav_data, "audio/wav")}
        data = {
            "title": f"Smoke Meeting {uid}",
            "consent_confirmed": "true",
            "source": "upload",
        }
        headers = {"Idempotency-Key": str(uuid.uuid4())}

        upload_res = client.post(
            "/api/v1/meetings",
            data=data,
            files=files,
            headers=headers,
        )
        if upload_res.status_code != 201:
            raise RuntimeError(f"Upload thất bại ({upload_res.status_code}): {upload_res.text}")
        payload = upload_res.json()
        meeting_id = payload["meeting"]["id"]
        job_id = payload["job"]["id"]
        print(f"   -> Upload thành công: meeting_id={meeting_id}, job_id={job_id}")

        # 5. Poll trạng thái job tới khi succeeded
        print("5. Theo dõi tiến trình xử lý job qua worker...")
        deadline = time.time() + timeout_sec
        job_success = False
        while time.time() < deadline:
            poll_res = client.get(f"/api/v1/jobs/{job_id}")
            if poll_res.status_code != 200:
                raise RuntimeError(f"Lỗi truy vấn job ({poll_res.status_code}): {poll_res.text}")
            res_json = poll_res.json()
            job_data = res_json.get("job", res_json)
            job_status = job_data["status"]
            stage = job_data.get("stage", "unknown")
            print(f"   ... trạng thái: {job_status} (giai đoạn: {stage})")

            if job_status == "succeeded":
                job_success = True
                break
            if job_status == "failed":
                raise RuntimeError(f"Job thất bại: {job_data.get('error')}")

            time.sleep(1.0)

        if not job_success:
            raise RuntimeError(f"Job không hoàn thành trong {timeout_sec}s.")
        print("   -> Job đã hoàn thành thành công (succeeded).")

        # 5.1 Kiểm tra thời lượng stage của worker xuất hiện trên /metrics (RE-018, BE-19)
        print("   -> Kiểm tra metric pipeline_stage_duration_seconds trên /metrics...")
        metrics_res = client.get("/metrics")
        if metrics_res.status_code != 200:
            raise RuntimeError(
                f"Truy vấn /metrics thất bại ({metrics_res.status_code}): {metrics_res.text}"
            )
        found_stage_duration = False
        for line in metrics_res.text.splitlines():
            if line.startswith("pipeline_stage_duration_seconds_count"):
                parts = line.rsplit(" ", 1)
                if len(parts) == 2:
                    with contextlib.suppress(ValueError):
                        if float(parts[1]) > 0.0:
                            found_stage_duration = True
                            break
        if not found_stage_duration:
            raise RuntimeError(
                "Không tìm thấy pipeline_stage_duration_seconds_count > 0 "
                "trên /metrics sau khi job hoàn thành."
            )
        print("   -> Đã xác nhận pipeline_stage_duration_seconds_count > 0 trên /metrics.")

        # 6. Tải export biên bản cuộc họp
        print("6. Tải bản xuất cuộc họp qua GET /api/v1/meetings/{id}/export...")
        export_txt = client.get(f"/api/v1/meetings/{meeting_id}/export?format=txt")
        if export_txt.status_code != 200:
            raise RuntimeError(f"Export txt lỗi ({export_txt.status_code}): {export_txt.text}")
        if len(export_txt.text) == 0:
            raise RuntimeError("Bản export txt rỗng.")

        export_json = client.get(f"/api/v1/meetings/{meeting_id}/export?format=json")
        if export_json.status_code != 200:
            raise RuntimeError(f"Export json lỗi ({export_json.status_code}): {export_json.text}")

        export_md = client.get(f"/api/v1/meetings/{meeting_id}/export?format=md")
        if export_md.status_code != 200:
            raise RuntimeError(f"Export md lỗi ({export_md.status_code}): {export_md.text}")
        print("   -> Tải xuất biên bản (TXT, JSON, MD) thành công.")

        # 7. Xóa cuộc họp và xóa tài khoản người dùng
        print("7. Dọn dẹp dữ liệu kiểm thử (DELETE meeting & user)...")
        del_meet = client.delete(f"/api/v1/meetings/{meeting_id}")
        if del_meet.status_code != 204:
            raise RuntimeError(f"Xóa meeting lỗi ({del_meet.status_code}): {del_meet.text}")

        del_user = client.delete("/api/v1/auth/me")
        if del_user.status_code != 204:
            raise RuntimeError(f"Xóa user lỗi ({del_user.status_code}): {del_user.text}")
        print("   -> Đã xóa meeting và user tổng hợp sạch sẽ.")

    print("\n=== SMOKE TEST THÀNH CÔNG: Toàn bộ quy trình End-to-End đã đạt ===")


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test end-to-end trên Docker Compose")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="URL gốc của API (mặc định: http://localhost:8000)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Thời gian timeout tối đa cho job (giây)",
    )
    args = parser.parse_args()

    try:
        run_smoke(args.base_url, timeout_sec=args.timeout)
    except Exception as exc:
        print(f"\n[THẤT BẠI] Smoke test gặp lỗi: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

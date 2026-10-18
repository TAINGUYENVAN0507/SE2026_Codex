"""AI/Speech pipeline cho Vietnamese Meeting Minutes Assistant.

Package này không biết gì về database hay HTTP. Worker của backend gọi
`runner.run_job()`, mỗi stage chạy trong một subprocess riêng và ghi kết quả
ra file JSON trong thư mục làm việc của job.
"""

__version__ = "0.1.0"

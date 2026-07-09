module.exports = {
  apps: [
    {
      name: "slide-api",
      script: ".venv/bin/uvicorn",
      interpreter: ".venv/bin/python",
      args: "backend.main:app --host 0.0.0.0 --port 8000",
      cwd: "/home/datn/ai-service",
      env: {
        PYTHONPATH: "backend",
        PYTHONUNBUFFERED: "1"
      },
      autorestart: true,
      watch: false,
      max_memory_restart: "1G"
    },
    {
      name: "slide-worker",
      script: "backend/worker.py",
      interpreter: ".venv/bin/python",
      cwd: "/home/datn/ai-service",
      instances: 2, // Số lượng worker chạy song song (bạn có thể tăng lên 3 hoặc 4)
      exec_mode: "fork",
      env: {
        PYTHONPATH: "backend"
      },
      autorestart: true,
      watch: false
    }
  ]
}

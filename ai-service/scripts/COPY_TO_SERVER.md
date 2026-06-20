# Đưa `sdxl_api_server.py` lên server GPU

Thay `USER`, `IP` (hoặc hostname), đường dẫn đích trên Linux (thường `~/` hoặc `/opt/sdxl/`).

## 1. SCP (từ máy Windows — PowerShell hoặc CMD)

Trong thư mục repo (hoặc chỉ rõ đường dẫn đầy đủ tới file):

```powershell
scp E:\DemoDoan\scripts\sdxl_api_server.py USER@IP:~/sdxl_api_server.py
```

SSH **không** dùng cổng 22 (ví dụ cổng `28895`):

```powershell
scp -P 28895 E:\DemoDoan\scripts\sdxl_api_server.py root@81.183.231.113:~/sdxl_api_server.py
scp -P 28895 E:\DemoDoan\scripts\requirements-sdxl-server.txt root@81.183.231.113:~/
# Giao diện web (/ui) — cần cả thư mục:
scp -P 28895 -r E:\DemoDoan\scripts\sdxl_static root@81.183.231.113:~/
```

(`scp` dùng **`-P` viết hoa**; `ssh` dùng **`-p` viết thường`.)

Nhiều file cùng thư mục `scripts`:

```powershell
scp E:\DemoDoan\scripts\sdxl_api_server.py USER@IP:~/ 
```

Trên server:

```bash
chmod +x ~/sdxl_api_server.py   # tùy chọn
```

## 2. Git (nếu repo DemoDoan đã push lên GitHub/GitLab)

Trên server:

```bash
git clone https://github.com/BAN/DemoDoan.git
cd DemoDoan/scripts
# python trong venv rồi: python sdxl_api_server.py
```

Nếu repo **private**: dùng SSH key hoặc token clone HTTPS.

## 3. SFTP (FileZilla, WinSCP, VS Code Remote)

- Host: `IP`, user/password hoặc key SSH.
- Kéo thả `scripts/sdxl_api_server.py` từ máy Windows sang thư mục trên server (vd. `/home/USER/`).

## 4. `scp` từ WSL / Git Bash (Windows)

```bash
scp /e/DemoDoan/scripts/sdxl_api_server.py USER@IP:~/
```

## 5. Sao chép nội dung thủ công

- Mở `sdxl_api_server.py` trong editor → copy toàn bộ → trên server: `nano ~/sdxl_api_server.py` → dán → lưu.

---

**Sau khi có file trên server:** tạo venv, cài **PyTorch CUDA** (theo [pytorch.org](https://pytorch.org)), rồi:

```bash
source ~/sdxl-venv/bin/activate
pip install -r requirements-sdxl-server.txt
# hoặc một dòng tối thiểu nếu chưa copy file requirements:
pip install fastapi "uvicorn[standard]" pillow diffusers transformers accelerate safetensors sentencepiece
```

**Linux không có lệnh `py`** — dùng `python` hoặc `python3`. Chạy API:

```bash
export SDXL_HOST=0.0.0.0
export SDXL_PORT=8080   # hoặc cổng khớp map của nhà cung cấp
python ~/sdxl_api_server.py
```

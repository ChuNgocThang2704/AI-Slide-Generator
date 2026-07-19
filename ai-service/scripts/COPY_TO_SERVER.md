# Deploy FLUX image server

From Windows PowerShell:

```powershell
cd E:\DemoDoan\ai-service
ssh -p 43794 root@185.62.108.226 "mkdir -p /root/ai-service/scripts"
scp -P 43794 scripts\flux_api_server.py root@185.62.108.226:/root/ai-service/scripts/
scp -P 43794 scripts\requirements-flux-server.txt root@185.62.108.226:/root/ai-service/scripts/
scp -P 43794 -r scripts\flux_static root@185.62.108.226:/root/ai-service/scripts/
```

On the GPU server:

```bash
cd /root/ai-service/scripts
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements-flux-server.txt
hf auth login

export FLUX_HOST=127.0.0.1
export FLUX_PORT=8080
export FLUX_MODEL_ID=black-forest-labs/FLUX.1-schnell
python flux_api_server.py
```

Keep the local tunnel open:

```powershell
ssh -N -p 43794 -L 8080:127.0.0.1:8080 root@185.62.108.226
```

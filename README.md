# ca business scraper api

setup
```bash
chmod +x setup.sh
./setup.sh
```

run
```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

health
```bash
curl http://localhost:8000/healthz
```

search
```bash
curl 'http://localhost:8000/search?term=1&limit=50'
```

csv files are saved under `data/`.

to debug with a visible browser
```bash
curl 'http://localhost:8000/search?term=1&limit=50&headless=false'
```

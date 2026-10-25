"""Start RoomLab locally; optionally read backend-only credentials from .env."""
from pathlib import Path
import os
import uvicorn

ROOT=Path(__file__).resolve().parents[1]
def main():
    env_file=ROOT/'.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key,value=line.split('=',1)
                if key.strip() in ('GEMINI_API_KEY','ROOMLAB_PORT','ROOMLAB_HOST'):
                    os.environ.setdefault(key.strip(),value.strip().strip('\"\x27'))
    uvicorn.run('backend.app.roomlab.main:app',host=os.environ.get('ROOMLAB_HOST','127.0.0.1'),port=int(os.environ.get('ROOMLAB_PORT','8001')))
if __name__=='__main__':main()

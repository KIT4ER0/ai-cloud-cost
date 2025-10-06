# ai-cloud-cost

run docker
 - docker compose up -d --build
 - docker ps

DB
 - docker cp db/schema.sql ai_cost_db:/schema.sql
   docker exec -it ai_cost_db psql -U ai_user -d ai_cost -f /schema.sql

etl
 - python -m etl.etl_cost
 - python -m etl.etl_metrics


API (FastAPI) → http://localhost:8000/health
UI (Streamlit) → http://localhost:8501
pgAdmin → http://localhost:5050
email: admin@example.com
password: admin123
Host: db , User: ai_user , Pass: ai_password
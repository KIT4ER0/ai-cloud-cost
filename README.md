# AI Cloud Cost Optimizer

An AI-driven cloud cost forecasting and simulation system. This project collects cloud metrics and cost data from AWS (EC2, RDS, Lambda, S3) and uses an ensemble machine learning approach (ETS, SARIMA, and Ridge algorithms with adaptive weighting) to predict future cloud costs. It also provides a comprehensive simulation and recommendation engine to help optimize cloud spending.

## 🚀 Key Features

- **AWS Data Sync:** Securely connects to AWS via Cross-Account IAM Roles and syncs CloudWatch Metrics & Cost Explorer data.
- **AI Forecasting Engine:** Utilizes ensemble models (ETS, SARIMA, Ridge) for highly accurate cost predictions with backtesting.
- **Cost Simulation:** Simulates various scenarios to project future costs based on infrastructural adjustments.
- **Recommendations:** Provides actionable insights and recommendations to minimize cloud expenses.
- **Full-Stack Dashboard:** FastAPI backend and React frontend for seamless management and visualization.

## 🛠 Tech Stack

- **Backend:** Python, FastAPI
- **Frontend:** React
- **Database:** PostgreSQL (managed via pgAdmin)
- **Infrastructure:** Docker & Docker Compose

## 📦 Getting Started

### 1. Start the Services

Run the entire application stack using Docker Compose:

```bash
docker compose up -d --build
```

You can verify the running containers using `docker ps`.

### 2. Initialize the Database

Copy the schema definition into the database container and execute it to create the required tables:

```bash
docker cp db/schema.sql ai_cost_db:/schema.sql
docker exec -it ai_cost_db psql -U ai_user -d ai_cost -f /schema.sql
```

## 🌐 Local Development Services

Once the containers are up and running, you can access the following services:

| Service | Local URL | Note |
| :--- | :--- | :--- |
| **UI (React)** | [http://localhost:5173](http://localhost:5173) | Main user interface |
| **API (FastAPI)** | [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI for API testing and documentation |
| **pgAdmin** | [http://localhost:5050](http://localhost:5050) | PostgreSQL administration interface |

### Database Credentials

To connect pgAdmin to the database, log in with the pgAdmin credentials, then add a new server using the DB credentials:

**pgAdmin Web Login:**
- **Email:** `admin@example.com`
- **Password:** `admin123`

**Database Connection Info (Inside pgAdmin):**
- **Host name/address:** `db`
- **Database:** `ai_cost`
- **Username:** `ai_user`
- **Password:** `ai_password`
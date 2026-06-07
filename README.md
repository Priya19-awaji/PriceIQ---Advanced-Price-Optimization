# PriceIQ Advanced Price Optimization

The Advanced Price Optimization system is a machine-learning driven platform designed for B2B wholesale pricing. It provides data-backed recommendations for SKU pricing to maximize net margin, factoring in complex B2B mechanisms like supplier and customer bonuses.

> [!NOTE]
> For a deep dive into the ML models, containerized deployment, and data flow, please see the [Technical Architecture Document](Technical_Architecture.md).

---

## 1. Getting the Data (Required)

Due to its size and security constraints, the large CSV dataset is **not** included in this GitHub repository. 

**Before running the application on any new laptop, you must:**
1. Open a web browser and log into your company's OneDrive.
2. Download the full dataset CSV file.
3. Place the downloaded CSV file into the `backend/Data/` folder.

---

## 2. Configuration (CSV vs SQL Server)

The application supports hot-swapping between the local CSV data and a live SQL Server database.

1. Navigate to the `backend/` directory.
2. Rename `.env.example` to `.env` (this file is ignored by git to protect your credentials).
3. Open `.env` and configure your credentials. 
   - Set `USE_SQL=True` to connect to your live database.
   - Set `USE_SQL=False` to fallback to the local CSV in `backend/Data/`.

---

## 3. Running with Docker (Recommended)

The easiest way to run the application across any environment is using Docker.

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

### Quick Start
1. Ensure your `.env` file is set up and your CSV is in `backend/Data/`.
2. Open a terminal in the root directory (where `docker-compose.yml` is located).
3. Run:
```bash
docker-compose up --build -d
```
4. Open your browser and navigate to `http://localhost:8080`.

To stop the containers:
```bash
docker-compose down
```

### Cleaning up Old Builds
If you rebuild the containers frequently, Docker keeps the older builds as "dangling" images, which can consume a lot of disk space over time. To clean up these unused older builds, run:
```bash
docker image prune -f
```
*(This command safely removes only the old builds that are not currently in use by any container).*

---

## 4. Local Development Without Docker

If you prefer to run the application natively for development purposes:

### Prerequisites
| Tool | Purpose | Installation |
|------|---------|-------------|
| **Miniconda** | Python environment management | [miniconda.io](https://docs.conda.io/en/latest/miniconda.html) |
| **Node.js** | Frontend build tooling | [nodejs.org](https://nodejs.org/) |

### Step 1: Backend (Terminal 1)
```bash
conda create -n priceop python=3.13 -y -c conda-forge --override-channels
conda activate priceop
cd backend
pip install -r requirements.txt
python api.py
```

### Step 2: Frontend (Terminal 2)
```bash
cd frontend
npm install
npm run dev -- --port 8080 --host
```

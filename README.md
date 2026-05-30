# PriceIQ Advanced Price Optimization - Technical Architecture

# PriceIQ Advanced Price Optimization

The Advanced Price Optimization system is a machine-learning driven platform designed for B2B wholesale pricing. It provides data-backed recommendations for SKU pricing to maximize net margin, factoring in complex B2B mechanisms like supplier and customer bonuses.

> [!NOTE]
> For a deep dive into the ML models, calculations, and data flow, please see the [Technical Architecture Document](Technical_Architecture.md).

---

## 1. Environment Setup

### Prerequisites

| Tool | Purpose | Installation |
|------|---------|-------------|
| **Miniconda** | Python environment management | [miniconda.io](https://docs.conda.io/en/latest/miniconda.html) |
| **Node.js** | Frontend build tooling | Bundled in `node-portable/` within the project folder, or install globally |

### Python Environment (Conda)

The Python backend runs inside a **conda environment named `priceop`**. This environment is managed externally via Miniconda (not stored inside the workspace) to keep the project folder lightweight.

**Key Python dependencies** (full list in `backend/requirements.txt`):
- `flask`, `flask-cors` (REST API server)
- `numpy`, `pandas`, `scipy`, `scikit-learn` (ML operations)
- `sqlalchemy`, `pyodbc` (SQL Server connection)

**To recreate the environment from scratch:**

```bash
conda create -n priceop python=3.13 -y -c conda-forge --override-channels
conda activate priceop
pip install -r backend/requirements.txt
```

### Node.js / Frontend Dependencies

Frontend dependencies are managed via `npm` and stored in `frontend/node_modules/`. To reinstall if missing:

```bash
cd frontend
npm install
```

---

## 2. Configuration (CSV vs SQL Server)

The application supports hot-swapping between local CSV data and a live SQL Server database.

1. Navigate to the `backend/` directory.
2. Rename `.env.example` to `.env` (this file is ignored by git to protect your credentials).
3. Open `.env` and configure your credentials. Set `USE_SQL=True` to connect to your database, or `USE_SQL=False` to fallback to the local CSV.

---

## 3. How to Run the Application

### Option A: Quick Start (via start.bat)

The simplest way to launch both backend and frontend together from the root directory:

```bash
start.bat
```

This script will automatically start the Flask backend on port 5001 and the React Vite frontend on port 8080.

### Option B: Run Backend & Frontend Separately (Recommended for Development)

**Terminal 1 — Backend (Flask API):**
```bash
conda activate priceop
cd backend
python api.py
```

**Terminal 2 — Frontend (React + Vite):**
```bash
cd frontend
npm run dev -- --port 8080 --host
```

---

## 4. Recent Fixes & UI Polish

The following critical UI/UX and backend integration fixes were recently implemented:

- **Monorepo Restructure:** Safely separated frontend and backend into isolated folders for easier Docker containerization and maintenance. Added SQL Server connector via SQLAlchemy.
- **Missing Component Added:** Integrated missing `toggle` component from `shadcn-ui`.
- **PGS Filter Contract Fixed:** Corrected a type mismatch (`type="pgs"` to `type="category"`) in `PgsAnalysisTab`.
- **Sticky Filter Bar Offset:** Fixed a scrolling overlap issue in `Index.tsx`. Changed `top-[104px]` to `top-0` to keep it flush.
- **Opaque Table Headers:** Modified the translucent background (`bg-muted/30`) of the Detailed Brand Metrics table header in `BrandAnalysisTab` to be solid (`bg-card`).

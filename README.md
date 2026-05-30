# PriceIQ Advanced Price Optimization - Technical Architecture

## 1. System Overview

The Advanced Price Optimization system is a machine-learning driven platform designed for B2B wholesale pricing. It provides data-backed recommendations for SKU pricing to maximize net margin, factoring in complex B2B mechanisms like supplier and customer bonuses.

### Core Objectives

- **Margin Maximization:** Recommend optimal price points using S-Curve demand elasticity models.
- **B2B Nuances:** Incorporate customer bonuses, EPD (Early Payment Discounts), and supplier bonuses into the margin calculation.
- **Explainability:** Present recommendations clearly with contextual KPIs, competitive insights, and risk metrics (e.g., substitution risk, cannibalization).

## 2. Architecture Layout

The application follows a clean, decoupled client-server architecture:

1. **Frontend (React + Vite)**: A Single Page Application (SPA) providing a highly interactive dashboard.
2. **Backend (Flask + Python)**: A stateless API server handling data ingestion, ML optimization, and KPI calculation.

### 2.1 Backend (Python / Flask)

- **`backend.py`**: The Flask application entry point. It exposes RESTful API endpoints (`/api/kpis`, `/api/monthly-trends`, `/api/pipeline`, etc.). Responses are cached in-memory for performance.
- **`data_model.py`**: Handles data ingestion from the source CSV. It aggregates metrics, calculates baselines, and ensures a single source of truth for all business logic and KPI calculations.
- **`price_optimizer.py`**: The core ML engine. It uses an S-Curve demand model to estimate price-volume elasticity per brand, category, and Product Group (PGS). It vectorizes operations over the SKU dataset to efficiently simulate price impacts and recommend optimal price points.

### 2.2 Frontend (React / TypeScript)

- **`pricing-engine.ts`**: The API client. It fetches data from the Flask backend and handles loading/error states.
- **`Index.tsx`**: The main orchestrator component. It maintains global application state (like the `bonusPct` slider) and renders the various dashboard tabs.
- **Dashboard Tabs**:
  - `BusinessOverviewTab`: High-level KPIs and monthly trends.
  - `CategoryAnalysisTab`: Performance grouped by category.
  - `BrandAnalysisTab`: Performance grouped by brand.
  - `PgsAnalysisTab`: Deep-dive into Product Groups.
  - `ProductInspectorTab`: Granular SKU-level insights, elasticity curves, and optimization recommendations.

## 3. Data Flow

1. **Initialization:** The Flask backend loads the B2B wholesale CSV file into a pandas DataFrame via `DataModel`.
2. **Pre-computation:** `PriceOptimizer` calculates base elasticities globally and hierarchically (Brand, Category, PGS).
3. **Client Request:** The React frontend fetches pre-computed KPIs, monthly trends, and optimization pipelines from the backend.
4. **Interactive Simulation:** When a user adjusts parameters (like the Customer Bonus percentage), the frontend re-fetches the pipeline, prompting the backend to re-run the vectorized SKU optimization with the new parameters.

## 4. Performance Optimizations

- **Vectorized ML Optimization:** SKU-level grid searches for optimal price points are entirely vectorized using NumPy arrays, achieving up to 10x performance improvements over iterative approaches.
- **In-Memory Caching:** Heavy API endpoints (`/api/kpis`, `/api/monthly-trends`, `/api/pipeline`) use dictionary-based caching keyed by parameters to guarantee sub-second response times for unchanged parameters.
- **Lean Frontend:** Unused Shadcn UI components, routing overhead, and legacy state variables have been aggressively pruned to reduce bundle size and component re-renders.

## 5. Security & Deployment

- **CORS:** The backend enables CORS to allow seamless communication with the frontend development server.
- **Statelessness:** The backend relies entirely on the loaded dataset and request parameters, making it easily horizontally scalable if deployed in a containerized environment (e.g., Docker/Kubernetes).

## 6. Environment Setup

### Prerequisites

| Tool | Purpose | Installation |
|------|---------|-------------|
| **Miniconda** | Python environment management | [miniconda.io](https://docs.conda.io/en/latest/miniconda.html) |
| **Node.js** | Frontend build tooling | Bundled in `node-portable/` within the project folder, or install globally |

### Python Environment (Conda)

The Python backend runs inside a **conda environment named `priceop`**. This environment is managed externally via Miniconda (not stored inside the workspace) to keep the project folder lightweight.

**Location:** `C:\Users\<username>\AppData\Local\miniconda3\envs\priceop`

**Key Python dependencies** (full list in `requirements.txt`):

| Package | Purpose |
|---------|---------|
| `flask`, `flask-cors` | REST API server |
| `numpy`, `pandas` | Data processing & computation |
| `scipy`, `scikit-learn` | Statistical & ML operations |
| `matplotlib`, `seaborn`, `plotly` | Visualization (data exploration) |
| `pyarrow` | Efficient DataFrame serialization |
| `streamlit` | Optional interactive data apps |
| `openpyxl` | Excel file support |

**To recreate the environment from scratch:**

```bash
conda create -n priceop python=3.13 -y -c conda-forge --override-channels
conda activate priceop
pip install -r requirements.txt
```

### Node.js / Frontend Dependencies

Frontend dependencies are managed via `npm` and stored in the standard `node_modules/` folder inside the project. To reinstall if missing:

```bash
cd "PriceIQ Advanced Price Optimization"
npm install
```

## 7. How to Run the Application

### Option A: Quick Start (via start.bat)

The simplest way to launch both backend and frontend together:

```bash
cd "PriceIQ Advanced Price Optimization"
start.bat
```

This script will:

1. Activate the `priceop` conda environment
2. Start the Flask backend on **port 5001** (minimized window)
3. Start the Vite frontend on **port 8080**
4. Open `http://localhost:8080` in your browser

### Option B: Run Backend & Frontend Separately (Recommended for Development)

Running them in separate terminals gives you better control over logs and debugging.

**Terminal 1 — Backend (Flask API):**

```bash
conda activate priceop
cd "PriceIQ Advanced Price Optimization"
python backend.py
```

The backend will:

- Load the CSV data and pre-compute the ML pipeline
- Serve the API at `http://localhost:5001`
- Log startup progress and any errors to the console

**Terminal 2 — Frontend (React + Vite):**

```bash
cd "PriceIQ Advanced Price Optimization"
npm run dev -- --port 8080 --host
```

The frontend will:

- Start a hot-reloading dev server at `http://localhost:8080`
- Proxy API calls to the Flask backend at `http://localhost:5001`

### Verifying Everything Works

1. **Backend health check:** Visit `http://localhost:5001/api/health` — should return `{"status": "ok", ...}`
2. **Frontend:** Visit `http://localhost:8080` — the PriceIQ dashboard should load with live data

## 8. Recent Fixes & UI Polish

The following critical UI/UX and backend integration fixes were recently implemented to improve stability and visual presentation:

- **Missing Component Added:** Integrated missing `toggle` component from `shadcn-ui` which was causing `toggle-group` resolution errors and preventing the app from compiling.
- **PGS Filter Contract Fixed:** Corrected a type mismatch (`type="pgs"` to `type="category"`) in `PgsAnalysisTab` and wired up the `pgs` query parameter in the `pricing-engine.ts` API client and `backend.py` routing, enabling accurate cross-elasticity filtering.
- **Sticky Filter Bar Offset:** Fixed a scrolling overlap issue in `Index.tsx`. The sticky filter bar was detaching and overlapping with KPI cards on scroll because its `top` offset (`top-[104px]`) was misaligned with the scroll container's boundary. Changed to `top-0` to keep it flush.
- **Opaque Table Headers:** Modified the translucent background (`bg-muted/30`) of the Detailed Brand Metrics table header in `BrandAnalysisTab` to be solid (`bg-card`). This prevents scrolling table rows from visually bleeding through the table header text.

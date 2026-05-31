# PriceIQ Advanced Price Optimization - Technical Architecture

## 1. System Overview

The Advanced Price Optimization system is a machine-learning driven platform designed for B2B wholesale pricing. It provides data-backed recommendations for SKU pricing to maximize net margin, factoring in complex B2B mechanisms like supplier and customer bonuses.

### Core Objectives
- **Margin Maximization:** Recommend optimal price points using S-Curve demand elasticity models.
- **B2B Nuances:** Incorporate customer bonuses, EPD (Early Payment Discounts), and supplier bonuses into the margin calculation.
- **Explainability:** Present recommendations clearly with contextual KPIs, competitive insights, and risk metrics (e.g., substitution risk, cannibalization).

## 2. Architecture Layout

The application is built as a **Monorepo** containing a clean, decoupled client-server architecture:

1. **Frontend (`frontend/`)**: A Single Page Application (SPA) built with React and Vite.
2. **Backend (`backend/`)**: A stateless API server built with Flask and Python.

### 2.1 Backend (Python / Flask)
- **`backend/core/sql_connector.py`**: Handles database connectivity via SQLAlchemy and PyODBC.
- **`backend/api.py`**: The Flask application entry point. Exposes RESTful API endpoints. Responses are cached in-memory for performance.
- **`backend/core/data_model.py`**: Handles data ingestion. It acts as a unified abstraction layer—fetching data from either SQL Server or a local CSV depending on the `.env` configuration.
- **`backend/core/price_optimizer.py`**: The core ML engine. Uses an S-Curve demand model to estimate price-volume elasticity.
- **`backend/tests/`**: Comprehensive test suite ensuring the robustness of the Flask API, data transformations, and ML edge cases.

### 2.2 Frontend (React / TypeScript)
- **`src/lib/pricing-engine.ts`**: The API client. Fetches data from the backend using relative paths (`/api/...`) to ensure Docker compatibility.
- **`src/pages/Index.tsx`**: The main orchestrator component maintaining global application state.
- **Dashboard Tabs**: Modular components for Business Overview, Category Analysis, Brand Analysis, PGS Analysis, and Product Inspector.

## 3. Data Flow & Hybrid Storage

1. **Configuration:** The `USE_SQL` environment variable dictates the data source.
2. **Initialization:** The backend connects to SQL Server (via `pyodbc`) or loads the local wholesale CSV file into a pandas DataFrame.
3. **Pre-computation:** Base elasticities are calculated globally and hierarchically (Brand, Category, PGS).
4. **Client Request:** The React frontend fetches pre-computed KPIs, monthly trends, and optimization pipelines.
5. **Interactive Simulation:** When a user adjusts parameters, the frontend re-fetches the pipeline, prompting the backend to re-run the vectorized SKU optimization.

## 4. Performance Optimizations

- **Vectorized ML Optimization:** SKU-level grid searches for optimal price points are entirely vectorized using NumPy arrays, achieving up to 10x performance improvements.
- **In-Memory Caching:** Heavy API endpoints use dictionary-based caching keyed by parameters to guarantee sub-second response times.
- **Multi-stage Docker Builds:** The frontend Dockerfile uses a multi-stage process (Node build -> Nginx serving) to keep production images tiny.

## 5. Docker & Deployment Architecture

The application is fully containerized using `docker-compose`, making it horizontally scalable and OS-agnostic.

- **Nginx Reverse Proxy:** The frontend container runs Nginx to serve the static React assets. Nginx is also configured to proxy all `/api/*` requests directly to the backend container (port 5001). This avoids CORS issues and ensures secure internal communication.
- **Data Volume Mounting:** The `backend/Data/` folder is mounted as a volume (`volumes: - ./backend/Data:/app/Data`). This allows developers to hot-swap CSV datasets on their host machine without needing to rebuild the Docker image.
- **Environment Management:** Database credentials and configuration toggles are safely managed via a `.env` file that Docker Compose injects directly into the backend container at runtime.

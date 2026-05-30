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


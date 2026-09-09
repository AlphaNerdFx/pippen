
# NBA Player Impact ML Model: Deployment Stack

## Executive Summary

This document provides deployment recommendations for the NBA player impact ML model, including model packaging, inference serving, containerization, orchestration, and monitoring.

**Recommended Stack:**

- **Model Registry:** MLflow Model Registry
- **Inference Server:** FastAPI + MLServer
- **Containerization:** Docker
- **Orchestration:** Kubernetes (KServe or Seldon Core)
- **Monitoring:** MLflow Model Monitoring + Evidently AI

---

## Phase 4: Deployment

### 4.1 Model Packaging & Registration

**Recommended Tools:**

- **MLflow Model Registry:**
  - Store model artifacts, metadata, and version information [SRC-146][SRC-154]
  - Track model lineage (which training run produced which model)
  - Manage model stages (Staging, Production, Archived)

**Workflow:**

```python
import mlflow

# Log model to MLflow
with mlflow.start_run():
    mlflow.xgboost.log_model(best_model, "model")
    mlflow.log_params(best_params)
    mlflow.log_metric("rmse", best_rmse)
  
# Register model
model_uri = f"runs:/{run_id}/model"
registered_model = mlflow.register_model(model_uri, "nba-player-impact-model")
```

---

### 4.2 Inference Server

**Recommended Stack: FastAPI + MLflow**

**Why FastAPI:**

- High-performance ASGI framework for Python [SRC-154][SRC-165]
- Automatic API documentation (Swagger UI)
- Async support for high-throughput inference
- MLflow provides built-in FastAPI inference server [SRC-154]

**Implementation:**

```python
from fastapi import FastAPI
import mlflow

app = FastAPI()
model = mlflow.pyfunc.load_model("models:/nba-player-impact-model/Production")

@app.post("/predict")
async def predict(player_features: dict):
    prediction = model.predict([player_features])
    return {"player_impact": prediction}
```

**Deployment Options:**

1. **Bare-bones FastAPI:**

   ```bash
   mlflow models serve -m models:/nba-player-impact-model/Production -h 0.0.0.0 -p 8080
   ```
2. **MLServer (for Kubernetes-native serving):**

   ```bash
   mlflow models build-docker -m models:/nba-player-impact-model/Production \
     -n nba-impact-model --enable-mlserver
   ```

   - MLServer integrates with **KServe** and **Seldon Core** for Kubernetes deployment [SRC-154][SRC-155][SRC-165]

---

### 4.3 Containerization & Orchestration

**Recommended Stack: Docker + Kubernetes**

**Docker:**

- Containerize model and inference server for consistent deployment [SRC-154][SRC-165]
- Command:
  ```bash
  mlflow models build-docker -m models:/nba-player-impact-model/Production \
    -n nba-impact-model --enable-mlserver
  ```

**Kubernetes:**

- Deploy to Kubernetes cluster using **KServe** or **Seldon Core** [SRC-154][SRC-155]
- Configuration file (KServe InferenceService):
  ```yaml
  apiVersion: serving.kserve.io/v1beta1
  kind: InferenceService
  metadata:
    name: nba-impact-model
  spec:
    predictor:
      sklearn:
        storageUri: s3://mlflow-models/nba-player-impact-model/Production
  ```
- Deploy:
  ```bash
  kubectl apply -f nba-impact-model.yaml
  ```

**AI-Assisted Tools:**

- **AutoML-Agent:** Generates deployment artifacts (Docker/cloud) and orchestrates deployment [SRC-150]
- **HCL AION:** Enterprise platform for deploying, monitoring, and scaling AI/ML models [SRC-145]

---

### 4.4 Model Monitoring & Drift Detection

**Why Monitor:**

- Catch performance declines early to ensure accurate predictions [SRC-156]
- Detect data drift (input feature distributions change over time)
- Detect prediction drift (model outputs shift)
- Trigger automated retraining when drift exceeds thresholds [SRC-158]

**Monitoring Pipeline:**

1. **Continuous Data Ingestion:**

   - Collect inference inputs and outputs at every prediction [SRC-156]
   - Store in time-series database (e.g., InfluxDB, TimescaleDB)
2. **Statistical Computation:**

   - Run **PSI (Population Stability Index)**, **KS (Kolmogorov-Smirnov)**, or **Chi-Squared** tests against baseline [SRC-156][SRC-158]
   - Schedule: every few minutes for real-time systems, daily for batch pipelines [SRC-156]
3. **Threshold Evaluation:**

   - Compare computed metrics against configured thresholds [SRC-156]
   - Emit structured events when limits exceeded
4. **Automated Response:**

   - Trigger retraining jobs, open incident tickets, or page on-call engineers [SRC-156][SRC-158]
   - Connect alerts to action (not just notifications) [SRC-161]
5. **Feedback Loop:**

   - Feed newly labeled data back into training pipeline [SRC-156][SRC-158]
   - Retrain using current ground truth, not stale historical data

**AI-Assisted Tools:**

- **Evidently AI:** Open-source drift detection library with PSI, KS tests [SRC-161]
- **MLflow Model Monitoring:** Built-in drift detection and alerting [SRC-156][SRC-158]
- **HCL AION:** Monitor, govern, and scale AI/ML models in production [SRC-145]

**Best Practices:**

- Set reference baseline at deploy time and monitor against it [SRC-161]
- Use drift as early-warning system, not sole indicator [SRC-161]
- Track real performance whenever labels arrive (e.g., actual EPM/RAPM updates) [SRC-161]
- Tune thresholds to avoid alert fatigue [SRC-161]
- Close loop to retraining (drift alerts should trigger retraining) [SRC-161]

---

## Deployment Stack Options

### Stack 1: Minimal Viable Deployment (MVP)

**Components:**

- **Model Training:** Python (scikit-learn, XGBoost) + Optuna
- **Model Registry:** MLflow (local or hosted)
- **Inference Server:** FastAPI (MLflow built-in)
- **Deployment:** Docker container on single VM
- **Monitoring:** Basic logging + MLflow model monitoring

**Use Case:** Prototyping, internal testing, low-traffic applications

**Pros:**

- Simple, low overhead
- Fast to deploy
- Easy to debug

**Cons:**

- Limited scalability
- Single point of failure
- Manual scaling

---

### Stack 2: Production-Grade Deployment

**Components:**

- **Model Training:** Python (XGBoost, LightGBM) + Optuna + MLflow
- **Model Registry:** MLflow Model Registry (hosted on cloud)
- **Inference Server:** FastAPI + MLServer
- **Containerization:** Docker
- **Orchestration:** Kubernetes (KServe or Seldon Core)
- **Monitoring:** MLflow Model Monitoring + Evidently AI + Prometheus/Grafana
- **CI/CD:** GitHub Actions or GitLab CI

**Use Case:** Production applications, high-traffic, mission-critical

**Pros:**

- Highly scalable
- Automated deployment and scaling
- Robust monitoring and alerting
- Fault-tolerant

**Cons:**

- Higher complexity
- Requires Kubernetes expertise
- More infrastructure overhead

---

### Stack 3: Enterprise-Grade Deployment

**Components:**

- **Model Training:** H2O Driverless AI or HCL AION
- **Model Registry:** HCL AION or MLflow Enterprise
- **Inference Server:** MLServer on Kubernetes
- **Orchestration:** Kubernetes (KServe)
- **Monitoring:** HCL AION (built-in monitoring, governance, drift detection)
- **CI/CD:** Enterprise CI/CD (Jenkins, GitLab Enterprise)
- **Governance:** HCL AION (model governance, compliance, audit trails)

**Use Case:** Enterprise applications, regulated industries, compliance requirements

**Pros:**

- End-to-end automation
- Built-in governance and compliance
- Enterprise support
- Integrated monitoring and alerting

**Cons:**

- Expensive (enterprise licensing)
- Vendor lock-in
- Less flexibility

---

## References

| ID      | Title                               | URL                                                                                   | Key Claims Supported                           |
| ------- | ----------------------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------- |
| SRC-145 | HCL AION                            | https://www.hcl-software.com/aion                                                     | Enterprise AI platform, deployment, monitoring |
| SRC-146 | Practitioners guide to MLOps        | https://services.google.com/fh/files/misc/practitioners_guide_to_mlops_whitepaper.pdf | MLOps best practices, deployment               |
| SRC-150 | AutoML-Agent                        | https://creati.ai/ai-tools/automl-agent/                                              | Deployment artifacts, orchestration            |
| SRC-154 | Develop ML model with MLflow        | https://mlflow.org/docs/latest/ml/deployment/deploy-model-to-kubernetes/tutorial/     | MLflow, FastAPI, Docker, Kubernetes, KServe    |
| SRC-155 | Develop ML model with MLflow        | https://mlflow.org/docs/3.3.0rc0/ml/deployment/deploy-model-to-kubernetes/tutorial/   | MLflow, KServe, Seldon Core                    |
| SRC-156 | Why Monitor Model Drift             | https://mlflow.org/articles/why-monitor-model-drift-production/                       | Drift monitoring, PSI, KS tests                |
| SRC-158 | Best practices for model monitoring | https://mlflow.org/articles/tags/best-practices-for-model-monitoring/                 | Model monitoring, drift detection              |
| SRC-161 | Model Monitoring in MLOps           | https://kodekloud.com/blog/model-monitoring-in-mlops/                                 | Evidently, drift detection, retraining         |
| SRC-165 | Deploy MLflow Model to Kubernetes   | https://mlflow.openml.io/docs/latest/ml/deployment/deploy-model-to-kubernetes/        | MLflow, FastAPI, MLServer, KServe              |

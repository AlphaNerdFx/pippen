# NBA Player Impact ML Model: AI-Tool Assistance by Stage

## Executive Summary

This document provides a comprehensive list of AI-assisted tools for each stage of the ML development pipeline, from data preparation through deployment and monitoring.

---

## AI Tools by Project Stage

| Stage | AI Tool | Function | Source |
|-------|---------|----------|--------|
| **Data Preparation** | Julius AI / ThoughtSpot | Automate data preprocessing, missing value handling, exploratory analysis | [SRC-153] |
| **Data Preparation** | AutoML-Agent | Automated data ingestion, exploratory analysis, missing value handling, feature engineering | [SRC-150] |
| **Feature Engineering** | AutoML-Agent | Automated feature selection, extraction, synthesis using LLM-driven agents | [SRC-141][SRC-150] |
| **Feature Engineering** | H2O Driverless AI | Automates feature engineering with Kaggle Masters expertise | [SRC-151] |
| **Feature Engineering** | TPOT | Automates feature engineering, algorithm selection, hyperparameter tuning | [SRC-148] |
| **Feature Engineering** | NewgenONE Platform | Automated feature engineering, model selection, hyperparameter tuning | [SRC-142] |
| **Model Selection** | AutoML-Agent | LLM-powered model architecture search | [SRC-150] |
| **Model Selection** | H2O Driverless AI | Automatically selects algorithms based on embedded expertise | [SRC-151] |
| **Model Selection** | SPIO | LLM-driven multi-agent planning for model selection | [SRC-141] |
| **Hyperparameter Tuning** | Optuna | Bayesian optimization with TPE algorithm | [SRC-169][SRC-173][SRC-179] |
| **Hyperparameter Tuning** | AutoML-Agent | LLM-powered hyperparameter optimization | [SRC-150] |
| **Hyperparameter Tuning** | HCL AION | Automated hyperparameter tuning with intelligent workflow automation | [SRC-145] |
| **Experiment Tracking** | MLflow | Track experiments, compare models, manage versions | [SRC-146][SRC-154] |
| **Model Interpretability** | SHAP | Global and local feature importance explanations | [SRC-176][SRC-178] |
| **Model Interpretability** | LIME | Local prediction explanations | [SRC-176][SRC-178] |
| **Deployment** | AutoML-Agent | Generate deployment artifacts (Docker/cloud), orchestrate deployment | [SRC-150] |
| **Deployment** | MLflow + FastAPI | Built-in FastAPI inference server, model serving | [SRC-154][SRC-165] |
| **Deployment** | HCL AION | Deploy, monitor, govern, scale AI/ML models | [SRC-145] |
| **Monitoring** | Evidently AI | Drift detection with PSI, KS tests | [SRC-161] |
| **Monitoring** | MLflow Model Monitoring | Built-in drift detection and alerting | [SRC-156][SRC-158] |
| **Monitoring** | HCL AION | Monitor and govern models in production | [SRC-145] |

---

## Detailed Tool Descriptions

### Data Preparation & Feature Engineering

**Julius AI / ThoughtSpot:**
- Automate data preprocessing, missing value handling, and exploratory analysis [SRC-153]
- Best for: Initial data exploration, quick insights
- Limitations: Less customizable than code-based approaches

**AutoML-Agent:**
- LLM-powered framework that handles data ingestion, exploratory analysis, feature engineering, model selection, hyperparameter tuning, and deployment [SRC-150]
- Best for: End-to-end automation with LLM-driven decision making
- Limitations: May require fine-tuning for domain-specific tasks

**H2O Driverless AI:**
- Automates feature engineering with Kaggle Masters expertise embedded into algorithms [SRC-151]
- Best for: Enterprise deployments, automated feature engineering
- Limitations: Commercial licensing, less flexibility

**TPOT:**
- Automates feature engineering, algorithm selection, and hyperparameter tuning using genetic programming [SRC-148]
- Best for: Automated pipeline generation
- Limitations: Can be slow for large datasets

**NewgenONE Platform:**
- Achieves optimal model performance with ML automatically selecting preprocessing, algorithms, and parameter configurations [SRC-142]
- Best for: Fully automated data science workflows
- Limitations: Commercial platform

---

### Model Selection & Hyperparameter Tuning

**SPIO (Sequential Plan Integration and Optimization):**
- LLM-driven framework that orchestrates multi-agent planning for model selection [SRC-141]
- Best for: Complex multi-stage ML workflows
- Limitations: Research-stage, may require customization

**Optuna:**
- Uses **Tree-structured Parzen Estimator (TPE)** for efficient Bayesian optimization [SRC-169][SRC-179][SRC-183]
- Adaptively selects hyperparameters based on previous evaluations [SRC-171][SRC-180]
- Supports pruning of unpromising trials [SRC-173]
- Integrates with MLflow for experiment tracking [SRC-177]
- Best for: Efficient hyperparameter optimization
- Limitations: Requires objective function definition

**HCL AION:**
- Enterprise platform with automated hyperparameter tuning and intelligent workflow automation [SRC-145]
- Best for: Enterprise deployments with governance requirements
- Limitations: Commercial licensing

---

### Model Interpretability

**SHAP (SHapley Additive exPlanations):**
- Provides both local and global explanations [SRC-176][SRC-178]
- Best for: Understanding feature contributions to predictions
- Limitations: Affected by feature collinearity; interpret with caution [SRC-178]

**LIME (Local Interpretable Model-agnostic Explanations):**
- Explains individual predictions by approximating complex model locally [SRC-176][SRC-178]
- Best for: Explaining specific predictions to stakeholders
- Limitations: Affected by feature collinearity; use with SHAP for robustness [SRC-178]

---

### Deployment & Monitoring

**MLflow + FastAPI:**
- Built-in FastAPI inference server for model serving [SRC-154][SRC-165]
- Best for: Simple, production-ready deployment
- Limitations: Requires additional tooling for Kubernetes-native deployment

**Evidently AI:**
- Open-source drift detection library with PSI, KS tests [SRC-161]
- Best for: Automated drift detection and alerting
- Limitations: Requires integration with monitoring pipeline

**HCL AION:**
- Enterprise platform for deploying, monitoring, governing, and scaling AI/ML models [SRC-145]
- Best for: Enterprise deployments with compliance requirements
- Limitations: Commercial licensing, vendor lock-in

---

## References

| ID | Title | URL | Key Claims Supported |
|----|-------|-----|---------------------|
| SRC-141 | SPIO: LLM-Based Multi-Agent Planning | https://arxiv.org/html/2503.23314v1 | LLM AutoML, multi-agent planning |
| SRC-142 | AI-first Automated Data Science | https://newgensoft.com/platform/artificial-intelligence-data-science/automated-data-science/ | NewgenONE automation |
| SRC-145 | HCL AION | https://www.hcl-software.com/aion | Enterprise AI platform |
| SRC-146 | Practitioners guide to MLOps | https://services.google.com/fh/files/misc/practitioners_guide_to_mlops_whitepaper.pdf | MLflow experiment tracking |
| SRC-148 | Automated Machine Learning | https://thecuberesearch.com/automated-machine-learning-assessing-available-solutions/ | TPOT |
| SRC-150 | AutoML-Agent | https://creati.ai/ai-tools/automl-agent/ | LLM AutoML framework |
| SRC-151 | H2O.ai | https://checkthat.ai/brands/h2o-ai | H2O Driverless AI |
| SRC-153 | Top AI Data Assistants | https://www.analyticsengineering.com/resources/best-ai-data-assistants-for-analytics-professionals | Julius AI, ThoughtSpot |
| SRC-154 | Develop ML model with MLflow | https://mlflow.org/docs/latest/ml/deployment/deploy-model-to-kubernetes/tutorial/ | MLflow FastAPI |
| SRC-156 | Why Monitor Model Drift | https://mlflow.org/articles/why-monitor-model-drift-production/ | MLflow monitoring |
| SRC-158 | Best practices for model monitoring | https://mlflow.org/articles/tags/best-practices-for-model-monitoring/ | MLflow drift detection |
| SRC-161 | Model Monitoring in MLOps | https://kodekloud.com/blog/model-monitoring-in-mlops/ | Evidently AI |
| SRC-165 | Deploy MLflow Model to Kubernetes | https://mlflow.openml.io/docs/latest/ml/deployment/deploy-model-to-kubernetes/ | MLflow MLServer |
| SRC-169 | Optuna: Next-generation Hyperparameter Optimization | https://dl.acm.org/doi/10.1145/3292500.3330701 | Optuna TPE |
| SRC-173 | Optuna Documentation | https://optuna.org/ | Optuna framework |
| SRC-176 | Interpretable Athlete Performance Modelling | https://www.techrxiv.org/doi/pdf/10.36227/techrxiv.177006540.07826863/v1 | SHAP, LIME |
| SRC-177 | Hyperparameter tuning with Optuna | https://learn.microsoft.com/en-us/azure/databricks/machine-learning/automl-hyperparam-tuning/optuna | Optuna + MLflow |
| SRC-178 | Explainable AI Methods | https://arxiv.org/html/2305.02012v3 | SHAP, LIME caveats |
| SRC-179 | Hyperparameter tuning with Optuna | https://medium.com/@fawwazmts/hyperparameter-tuning-with-optuna-8e806b654f90 | Optuna Bayesian optimization |
| SRC-180 | Machine Learning Optimization with Optuna | https://medium.com/data-science/machine-learning-optimization-with-optuna-57593d700e52 | Optuna guide |
| SRC-183 | Bayesian Sorcery for Hyperparameter Optimization | https://medium.com/@becaye-balde/bayesian-sorcery-for-hyperparameter-optimization-using-optuna-1ee4517e89a | Optuna TPE |
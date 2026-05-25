# GCP Deployment Guide - PowerShell

## Prerequisites
- gcloud CLI installed
- Docker installed
- kubectl installed
- GCP project with GKE enabled

## 1. Build and Push Docker Image

```powershell
# Set your project and region
$env:PROJECT_ID="project-953fdbff-8291-4198-9c5"
$env:REGION="us-central1"
$env:IMAGE_NAME="doc-intelligence"

# Authenticate to Google Container Registry
gcloud auth configure-docker ${env:REGION}-docker.pkg.dev

# Build the image
docker build -t ${env:REGION}-docker.pkg.dev/${env:PROJECT_ID}/doc-intelligence/${env:IMAGE_NAME}:latest .

# Push to Artifact Registry
docker push ${env:REGION}-docker.pkg.dev/${env:PROJECT_ID}/doc-intelligence/${env:IMAGE_NAME}:latest
```

## 2. Create GKE Cluster (if not exists)

```powershell
gcloud container clusters create doc-intelligence-cluster `
    --region=${env:REGION} `
    --num-nodes=2 `
    --machine-type=e2-standard-2 `
    --enable-autoscaling `
    --min-nodes=1 `
    --max-nodes=5
```

## 3. Edit deployment.yaml

Open `k8s/deployment.yaml` and replace:
- `PROJECT_ID` with your actual project ID
- `REGION` with your region (e.g., `us-central1`)

## 4. Apply Kubernetes Deployment

```powershell
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

## 5. Verify Deployment

```powershell
# Check pods
kubectl get pods -l app=doc-intelligence

# Check service
kubectl get svc doc-intelligence

# View logs
kubectl logs -l app=doc-intelligence
```

## 6. Create Secrets

```powershell
# Create secret for GCP service account
kubectl create secret generic google-sa-key `
    --from-file=key.json=path-to-your-service-account-key.json

# Create secret for project ID
kubectl create secret generic doc-intelligence-secrets `
    --from-literal=project-id=$env:PROJECT_ID
```

## 7. Expose Service (LoadBalancer)

```powershell
kubectl expose deployment doc-intelligence `
    --name=doc-intelligence-lb `
    --type=LoadBalancer `
    --port=80 `
    --target-port=8080
```

Then get the external IP:
```powershell
kubectl get svc doc-intelligence-lb
```

## 8. Horizontal Pod Autoscaler

```powershell
kubectl autoscale deployment doc-intelligence `
    --cpu-percent=70 `
    --min=1 `
    --max=10
```

## Quick Complete Commands

```powershell
# Build and push
$env:PROJECT_ID="your-project-id"
$env:REGION="us-central1"
docker build -t ${env:REGION}-docker.pkg.dev/${env:PROJECT_ID}/doc-intelligence/doc-intelligence:latest .
docker push ${env:REGION}-docker.pkg.dev/${env:PROJECT_ID}/doc-intelligence/doc-intelligence:latest

# Deploy
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl expose deployment doc-intelligence --name=doc-intelligence-lb --type=LoadBalancer --port=80 --target-port=8080
```
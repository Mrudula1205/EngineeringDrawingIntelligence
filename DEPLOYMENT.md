# GCP Deployment Guide

## Prerequisites
- gcloud CLI installed
- Docker installed
- kubectl installed
- GCP project with GKE enabled

## 1. Build and Push Docker Image

```bash
# Set your project and region
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
export IMAGE_NAME="doc-intelligence-backend"
export TAG="latest"

# Authenticate to Google Container Registry
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Build the image
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${IMAGE_NAME}/${IMAGE_NAME}:${TAG} .

# Push to Artifact Registry
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${IMAGE_NAME}/${IMAGE_NAME}:${TAG}
```

## 2. Create GKE Cluster (if not exists)

```bash
gcloud container clusters create doc-intelligence-cluster \
    --region=${REGION} \
    --num-nodes=2 \
    --machine-type=e2-standard-2 \
    --enable-autoscaling \
    --min-nodes=1 \
    --max-nodes=5
```

## 3. Apply Kubernetes Deployment

Replace `your-gcp-project-id` in `deployment.yaml` with your actual project ID, then:

```bash
kubectl apply -f k8s/deployment.yaml
```

## 4. Verify Deployment

```bash
# Check pods
kubectl get pods -l app=doc-intelligence

# Check service
kubectl get svc doc-intelligence

# View logs
kubectl logs -l app=doc-intelligence
```

## 5. Setup Ingress (optional - for HTTPS)

```bash
kubectl apply -f k8s/ingress.yaml
```

## 6. Configure Environment Variables

Create a Secret for sensitive env vars:
```bash
kubectl create secret generic doc-intelligence-secrets \
    --from-literal=GOOGLE_APPLICATION_CREDENTIALS="$(cat service-account-key.json | base64)" \
    --from-literal=FIRESTORE_EMULATOR_HOST="" \
    --from-literal=GOOGLE_CLOUD_PROJECT="${PROJECT_ID}"
```

## 7. Set up Horizontal Pod Autoscaler

```bash
kubectl autoscale deployment doc-intelligence \
    --cpu-percent=70 \
    --min=1 \
    --max=10
```

## 8. Update Service Account (Recommended)

Create a dedicated service account for the application:
```bash
gcloud iam service-accounts create doc-intelligence-sa \
    --display-name="Doc Intelligence Service Account"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:doc-intelligence-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

gcloud iam service-accounts keys create sa-key.json \
    --iam-account=doc-intelligence-sa@${PROJECT_ID}.iam.gserviceaccount.com

kubectl create secret generic google-sa-key \
    --from-file=key.json=sa-key.json
```
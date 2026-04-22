# Guestbook — Kubernetes Demo App

A three-tier demo application: **Frontend** (Nginx + HTML/JS) → **Backend** (PHP API) → **Database** (Redis). Deployed on Kubernetes via Helm.

---

## Architecture

```
Browser
   │
   ▼
┌─────────────────────────────────┐
│  Frontend  (nginx:alpine)       │  NodePort :30080
│  Serves HTML, proxies /api/     │
└──────────────┬──────────────────┘
               │ http://guestbook-backend:80
               ▼
┌─────────────────────────────────┐
│  Backend  (gb-frontend:v5)      │  ClusterIP
│  PHP app, REST API              │
└──────────────┬──────────────────┘
               │ redis://redis-leader:6379
               ▼
┌─────────────────────────────────┐
│  Database  (redis:7-alpine)     │  ClusterIP
│  Stores guestbook messages      │
└─────────────────────────────────┘
```

| Component | Image | Service Type | Port |
|-----------|-------|--------------|------|
| frontend | `nginx:alpine` | NodePort | 30080 |
| backend | `gcr.io/google-samples/gb-frontend:v5` | ClusterIP | 80 |
| database | `redis:7-alpine` | ClusterIP | 6379 |

---

## Requirements

To run this on **Windows 10 / Windows 11** you need to install:

1. WSL2 (Windows Subsystem for Linux)
2. Docker Desktop
3. minikube
4. kubectl
5. Helm

Everything is installed once. After that it's just `helm install`.

---

## Part 1 — Environment Setup

### 1.1 Enable Hardware Virtualization (BIOS/UEFI)

Virtualization is required for WSL2 and minikube. On most modern PCs it is enabled by default, but on some machines it must be turned on manually.

**How to check:**
1. Open **Task Manager** → **Performance** tab → **CPU**
2. Find the **Virtualization** row — it must say **Enabled**

If it says **Disabled** — reboot your PC, enter BIOS (usually `Del`, `F2`, or `F10` at startup) and find the setting **Intel VT-x** / **AMD-V** / **SVM Mode** — enable it.

---

### 1.2 Install WSL2

WSL2 lets you run Linux inside Windows without a separate virtual machine. Docker Desktop and minikube rely on it as their foundation.

**Open PowerShell as Administrator** (right-click Start menu → Windows PowerShell (Administrator)):

```powershell
# Install WSL2 with Ubuntu in one command
wsl --install

# Reboot after installation
Restart-Computer
```

After the reboot an Ubuntu window will open automatically. Set a username and password (this is a local Linux user, unrelated to your Windows account).

**Verify the installation:**
```powershell
wsl --list --verbose
```
Expected output:
```
  NAME      STATE           VERSION
* Ubuntu    Running         2
```

The number `2` in the VERSION column confirms WSL2. If you see `1`, upgrade with:
```powershell
wsl --set-version Ubuntu 2
```

> **Note:** If `wsl --install` fails (older Windows build), follow the manual WSL2 installation guide at:
> https://learn.microsoft.com/en-us/windows/wsl/install-manual

---

### 1.3 Install Docker Desktop

Docker Desktop is the container runtime. minikube will use it as its driver.

1. Download the installer: **https://www.docker.com/products/docker-desktop/**
2. Run `Docker Desktop Installer.exe`
3. During installation, make sure the checkbox **"Use WSL 2 instead of Hyper-V"** is checked
4. Reboot when prompted

**Configure Docker Desktop:**
1. Open Docker Desktop
2. Go to **Settings → Resources → WSL Integration**
3. Enable integration for your Ubuntu distro (the toggle must be ON)
4. Click **Apply & Restart**

**Verify** (in PowerShell or the Ubuntu terminal):
```bash
docker --version
# Docker version 27.x.x, build ...

docker run hello-world
# Hello from Docker! — everything works
```

---

### 1.4 Install kubectl

`kubectl` is the command-line tool for managing a Kubernetes cluster.

Open an **Ubuntu terminal** (from the Start menu or type `wsl` in PowerShell) and run:

```bash
# Download the latest stable release
curl -LO "https://dl.k8s.io/release/$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

# Make it executable and move to PATH
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Verify
kubectl version --client
# Client Version: v1.xx.x
```

Alternatively, install via `snap` (simpler):
```bash
sudo snap install kubectl --classic
kubectl version --client
```

---

### 1.5 Install minikube

minikube runs a single-node Kubernetes cluster locally — perfect for development and demos.

In the **Ubuntu terminal**:

```bash
# Download the minikube binary
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64

# Install it
sudo install minikube-linux-amd64 /usr/local/bin/minikube
rm minikube-linux-amd64

# Verify
minikube version
# minikube version: v1.xx.x
```

---

### 1.6 Install Helm

Helm is the package manager for Kubernetes. It deploys applications via reusable templates called **charts**.

In the **Ubuntu terminal**:

```bash
# Official install script
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify
helm version
# version.BuildInfo{Version:"v3.xx.x", ...}
```

---

## Part 2 — Start the Kubernetes Cluster

### 2.1 Start minikube

Open the **Ubuntu terminal** and run:

```bash
# Start a cluster using Docker as the driver
minikube start --driver=docker --nodes 3 --cpus 2 --memory 4096
```

**Verify the cluster:**
```bash
# Check cluster info
kubectl cluster-info
# Kubernetes control plane is running at https://127.0.0.1:xxxxx

# Check system pods (all should be Running)
kubectl get pods -n kube-system
```

---

## Part 3 — Deploy the Application

### 3.1 Get the chart files

Clone the repository or copy the `examples/k8s/` folder to your machine:

```bash
git clone <repository-url>
cd <repository>/examples/k8s
```

Verify you see the three chart folders:
```bash
ls
# backend/   database/   frontend/   README.md
```

---

### 3.2 Create a namespace (recommended)

A namespace is an isolated workspace inside the cluster — it keeps all app resources grouped together and easy to manage.

```bash
kubectl create namespace guestbook

# Make it the default namespace for the current context
kubectl config set-context --current --namespace=guestbook
```

You can skip this step; everything will be installed in the `default` namespace instead.

---

### 3.3 Install the charts (order matters)

**Step 1 — Database (Redis):**
```bash
helm install gb-database ./database -n guestbook

# Verify the pod started
kubectl get pods -n guestbook
# NAME                            READY   STATUS    RESTARTS   AGE
# redis-leader-xxxxxxxxx-xxxxx    1/1     Running   0          30s
```

Wait for `Running` status before the next step. `ContainerCreating` just means the image is still downloading.

**Step 2 — Backend (PHP API):**
```bash
helm install gb-backend ./backend -n guestbook

kubectl get pods -n guestbook
# guestbook-backend-xxx should appear with status Running
```

**Step 3 — Frontend (Nginx):**
```bash
helm install gb-frontend ./frontend -n guestbook

kubectl get pods -n guestbook
# guestbook-frontend-xxx should appear with status Running
```

---

### 3.4 Verify all components are running

```bash
# All pods should be Running
kubectl get pods -n guestbook
# NAME                                  READY   STATUS    RESTARTS   AGE
# guestbook-backend-75d9f6c8c9-xxxxx    1/1     Running   0          2m
# guestbook-frontend-6b8f7d9b4-xxxxx    1/1     Running   0          1m
# redis-leader-7c4b9f8d5-xxxxx          1/1     Running   0          3m

# All services should be created
kubectl get services -n guestbook
# NAME                  TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)          AGE
# guestbook-backend     ClusterIP   10.96.xxx.xxx    <none>        80/TCP           2m
# guestbook-frontend    NodePort    10.96.xxx.xxx    <none>        80:30080/TCP     1m
# redis-leader          ClusterIP   10.96.xxx.xxx    <none>        6379/TCP         3m
```

---

## Part 4 — Open the Application in the Browser

### Option A — Via minikube service (recommended)

```bash
minikube service guestbook-frontend -n guestbook
```

minikube will automatically open your browser at the correct URL. If the browser does not open, the URL is printed to the console.

### Option B — Via IP and port manually

```bash
# Get minikube IP
minikube ip
# e.g.: 192.168.49.2
```

Open in your browser: `http://192.168.49.2:30080`

> **WSL2 note:** The minikube IP may not be directly reachable from the Windows browser. Use Option A or Option C in that case.

### Option C — Via port-forward (always works)

```bash
kubectl port-forward service/guestbook-frontend 8080:80 -n guestbook
```

Open in your browser: `http://localhost:8080`

Keep the terminal window with this command open while using the app.

---

## NEXT STEPS ARE OPTINAL AND NOT MANDATORY, JUST FOR INFO 

## Part 5 — Managing the Application

### View logs

```bash
# Backend logs
kubectl logs -l app.kubernetes.io/name=guestbook-backend -n guestbook

# Frontend logs
kubectl logs -l app.kubernetes.io/name=guestbook-frontend -n guestbook

# Database logs
kubectl logs -l app.kubernetes.io/name=guestbook-database -n guestbook

# Stream logs in real time
kubectl logs -f -l app.kubernetes.io/name=guestbook-backend -n guestbook
```

### Update a chart without reinstalling

```bash
# For example, scale the backend to 3 replicas
helm upgrade gb-backend ./backend -n guestbook --set replicaCount=3

# Or after editing values.yaml
helm upgrade gb-backend ./backend -n guestbook -f ./backend/values.yaml
```

### List installed Helm releases

```bash
helm list -n guestbook
# NAME           NAMESPACE   REVISION  STATUS    CHART
# gb-database    guestbook   1         deployed  guestbook-database-0.1.0
# gb-backend     guestbook   1         deployed  guestbook-backend-0.1.0
# gb-frontend    guestbook   1         deployed  guestbook-frontend-0.1.0
```

### Stop minikube (preserves state)

```bash
minikube stop
```

### Start minikube again

```bash
minikube start
# All pods will come back up automatically
```

### Remove the application (keep the cluster)

```bash
helm uninstall gb-frontend gb-backend gb-database -n guestbook
kubectl delete namespace guestbook
```

### Delete the cluster entirely

```bash
minikube delete
# All data removed, cluster destroyed
```

---

## Part 6 — Troubleshooting

### Pod is stuck in `Pending`

```bash
kubectl describe pod <pod-name> -n guestbook
```

The most common cause is insufficient resources. Increase minikube limits:
```bash
minikube stop
minikube start --cpus=4 --memory=4096
```

### Pod shows `ImagePullBackOff` or `ErrImagePull`

The image cannot be pulled. Check your internet connection and Docker Hub availability:
```bash
docker pull redis:7-alpine
docker pull nginx:alpine
```

### Backend cannot connect to Redis

Make sure the `redis-leader` service exists:
```bash
kubectl get service redis-leader -n guestbook
```

If it is missing, the `database` chart was not installed. Install it and restart the backend:
```bash
helm install gb-database ./database -n guestbook
kubectl rollout restart deployment/guestbook-backend -n guestbook
```

### Page loads but messages do not appear

Check that nginx is successfully proxying requests to the backend:
```bash
kubectl exec -it deployment/guestbook-frontend -n guestbook -- \
  wget -qO- "http://guestbook-backend/guestbook.php?cmd=get"
# Should return: {"data": ""}
```

### `minikube service` does not open the browser in WSL2

This is a WSL2 limitation — the Windows browser is not integrated with Linux. Use port-forward instead:
```bash
kubectl port-forward service/guestbook-frontend 8080:80 -n guestbook
# Open: http://localhost:8080
```

### `minikube start` hangs or fails

Reset and recreate the cluster:
```bash
minikube delete
minikube start --driver=docker
```

---

## Quick Start Cheatsheet

```bash
# 1. Start the cluster
minikube start --driver=docker

# 2. Create a namespace
kubectl create namespace guestbook

# 3. Deploy all three components
helm install gb-database ./database -n guestbook
helm install gb-backend  ./backend  -n guestbook
helm install gb-frontend ./frontend -n guestbook

# 4. Wait until all pods are Running
kubectl get pods -n guestbook --watch

# 5. Open in the browser
minikube service guestbook-frontend -n guestbook
```

---

## File Structure

```
examples/k8s/
├── README.md                        ← this file
├── database/                        ← Helm chart for Redis
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── _helpers.tpl
│       ├── deployment.yaml
│       └── service.yaml
├── backend/                         ← Helm chart for PHP API
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── _helpers.tpl
│       ├── deployment.yaml
│       └── service.yaml
└── frontend/                        ← Helm chart for Nginx + UI
    ├── Chart.yaml
    ├── values.yaml
    └── templates/
        ├── _helpers.tpl
        ├── configmap.yaml           ← nginx.conf + index.html
        ├── deployment.yaml
        ├── service.yaml
        └── ingress.yaml
```

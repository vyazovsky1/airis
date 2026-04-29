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

| Component | Image | Kind | Service Type | Port |
|-----------|-------|------|--------------|------|
| frontend | `nginx:alpine` | Deployment | NodePort | 30080 |
| backend | `gcr.io/google-samples/gb-frontend:v5` | Deployment | ClusterIP | 80 |
| database | `redis:7-alpine` | **StatefulSet** | ClusterIP | 6379 |
| log-collector | `fluent/fluent-bit:3.2` | **DaemonSet** | — | — |

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

sudo apt  install docker.io
sudo usermod -aG docker $USER && newgrp docker

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

### 2.2 Install Metrics Server

The **Metrics Server** collects real-time CPU and memory usage from every node and pod. It is required for `kubectl top` and for Horizontal Pod Autoscaler to work. minikube does not ship it by default.

**Step 1 — Deploy Metrics Server:**
```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

**Step 2 — Patch for minikube (disable TLS verification):**

minikube uses self-signed kubelet certificates. Without this patch, Metrics Server cannot connect to kubelets and stays in `CrashLoopBackOff`.

```bash
kubectl patch deployment metrics-server -n kube-system \
  --type='json' \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
```

**Verify it is running (wait ~30 seconds after the patch):**
```bash
kubectl get deployment metrics-server -n kube-system
# NAME             READY   UP-TO-DATE   AVAILABLE   AGE
# metrics-server   1/1     1            1           1m

# Check that node metrics are available
kubectl top nodes
# NAME           CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%
# minikube       210m         10%    850Mi           21%
# minikube-m02   130m         6%     620Mi           15%
```

Once ready, you can inspect live resource consumption for all guestbook pods:
```bash
kubectl top pods -n guestbook
# NAME                                   CPU(cores)   MEMORY(bytes)
# guestbook-backend-75d9f6c8c9-xxxxx     2m           38Mi
# guestbook-frontend-6b8f7d9b4-xxxxx     1m           12Mi
# redis-leader-0                         3m           9Mi
```

---

## Part 3 — Deploy the Application

### 3.1 Get the chart files

Clone the repository or copy the `examples/k8s/` folder to your machine:

```bash
git clone <repository-url>
cd <repository>/examples/k8s
```

Verify the folder structure:
```bash
ls
# backend/  database/  deploy.sh  frontend/  log-collector/  monitoring/  README.md
```

> **One-command deploy:** `deploy.sh` installs or removes the entire application in one step — see [3.2 Using the deploy script](#32-using-the-deploy-script).

---

### 3.2 Using the deploy script

`deploy.sh` is the fastest way to get the full stack running. Run it from the `examples/k8s/` directory:

```bash
# Make it executable (once)
chmod +x deploy.sh

# Deploy everything (creates the namespace automatically)
./deploy.sh up

# Deploy app + Prometheus/Grafana monitoring stack
./deploy.sh up --monitoring

# Show current state (pods, services, PVCs, Helm releases)
./deploy.sh status

# Remove everything (namespace deleted, PVCs kept for safety)
./deploy.sh down

# Remove everything including StatefulSet PVCs (all Redis data lost)
./deploy.sh down --delete-pvcs
```

The script installs charts **in dependency order** and waits for each workload to become ready before moving on. Use a custom namespace with `-n`:

```bash
./deploy.sh up -n my-namespace
```

Skip to [Part 4](#part-4--open-the-application-in-the-browser) once the script finishes.

---

### 3.3 Manual install (chart by chart)

If you prefer to install charts one at a time:

#### Create a namespace (recommended)

A namespace is an isolated workspace inside the cluster — it keeps all app resources grouped together and easy to manage.

```bash
kubectl create namespace guestbook

# Make it the default namespace for the current context
kubectl config set-context --current --namespace=guestbook
```

You can skip this step; everything will be installed in the `default` namespace instead.

A namespace is an isolated workspace inside the cluster — it keeps all app resources grouped together and easy to manage.

```bash
kubectl create namespace guestbook

# Make it the default namespace for the current context
kubectl config set-context --current --namespace=guestbook
```

You can skip this step; everything will be installed in the `default` namespace instead.

---

#### Install the charts (order matters)

**Step 1 — Database (Redis StatefulSet):**
```bash
helm install gb-database ./database -n guestbook

# Verify the pod started
kubectl get pods -n guestbook
# NAME             READY   STATUS    RESTARTS   AGE
# redis-leader-0   1/1     Running   0          30s
```

> **Why StatefulSet?** Unlike a Deployment, a StatefulSet gives each pod a **stable, predictable name** (`redis-leader-0`, `redis-leader-1`, ...) and creates a **dedicated PVC per pod** via `volumeClaimTemplates`. This guarantees that after a restart the pod always reconnects to the same data — essential for databases.

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

#### Verify all components are running

```bash
# All pods should be Running
kubectl get pods -n guestbook
# NAME                                  READY   STATUS    RESTARTS   AGE
# guestbook-backend-75d9f6c8c9-xxxxx    1/1     Running   0          2m
# guestbook-frontend-6b8f7d9b4-xxxxx    1/1     Running   0          1m
# redis-leader-0                        2/2     Running   0          3m   ← StatefulSet pod

# All services should be created
kubectl get services -n guestbook
# NAME                      TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)          AGE
# guestbook-backend         ClusterIP   10.96.xxx.xxx    <none>        80/TCP           2m
# guestbook-frontend        NodePort    10.96.xxx.xxx    <none>        80:30080/TCP     1m
# redis-leader              ClusterIP   10.96.xxx.xxx    <none>        6379/TCP         3m
# redis-leader-headless     ClusterIP   None             <none>        6379/TCP         3m  ← headless

# StatefulSet-managed PVC (created automatically by volumeClaimTemplates)
kubectl get pvc -n guestbook
# NAME                       STATUS   VOLUME   CAPACITY   AGE
# redis-data-redis-leader-0  Bound    ...      1Gi        3m
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
helm uninstall gb-frontend gb-backend gb-database gb-logs -n guestbook
kubectl delete namespace guestbook

# StatefulSet PVCs are NOT deleted automatically (data protection).
# To delete them explicitly:
kubectl delete pvc -l app.kubernetes.io/name=guestbook-database -n guestbook
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
minikube start --driver=docker --nodes 3 --cpus 2 --memory 4096

# 2. Install Metrics Server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch deployment metrics-server -n kube-system \
  --type='json' \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

# 3. Deploy everything with one command
chmod +x deploy.sh
./deploy.sh up

# 4. Open in the browser
minikube service guestbook-frontend -n guestbook

# 5. Useful commands after deploy
kubectl top nodes                          # node CPU/RAM (needs Metrics Server)
kubectl top pods -n guestbook             # pod CPU/RAM
kubectl get pods -n guestbook -o wide     # all pods with node placement
kubectl logs -l app.kubernetes.io/instance=gb-logs -n guestbook -f  # collector logs

# 6. Tear down
./deploy.sh down --delete-pvcs
```

---

## Part 7 — DaemonSet: Log Collector (Fluent Bit)

A **DaemonSet** ensures that exactly **one pod runs on every node** in the cluster. When a new node joins, Kubernetes automatically schedules the DaemonSet pod on it — no manual intervention needed. Typical uses: log shipping, metrics agents, security scanners, CNI plugins.

```
 Node 1            Node 2            Node 3
┌──────────┐      ┌──────────┐      ┌──────────┐
│fluent-bit│      │fluent-bit│      │fluent-bit│  ← one per node, always
│ reads    │      │ reads    │      │ reads    │
│/var/log  │      │/var/log  │      │/var/log  │
└──────────┘      └──────────┘      └──────────┘
```

The `log-collector/` chart deploys Fluent Bit as a DaemonSet. It:
- Reads all container logs from `/var/log/containers/` on each node via a `hostPath` volume
- Enriches log lines with pod name, namespace, and labels by querying the Kubernetes API
- Prints enriched JSON to stdout (visible via `kubectl logs`)

### 7.1 Deploy the log collector

```bash
helm install gb-logs ./log-collector -n guestbook
```

Wait for one pod per node:

```bash
kubectl get pods -n guestbook -l app.kubernetes.io/name=guestbook-log-collector -o wide
# NAME                                READY   STATUS    NODE
# gb-logs-guestbook-log-collector-xxx 1/1     Running   minikube
# gb-logs-guestbook-log-collector-yyy 1/1     Running   minikube-m02
# gb-logs-guestbook-log-collector-zzz 1/1     Running   minikube-m03
```

### 7.2 Inspect collected logs

```bash
# Stream enriched logs from all collector pods
kubectl logs -l app.kubernetes.io/name=guestbook-log-collector -n guestbook -f
```

Each line is a JSON object that includes the original log message plus Kubernetes metadata:

```json
{
  "log": "GET /guestbook.php?cmd=get HTTP/1.1",
  "kubernetes": {
    "pod_name": "guestbook-backend-75d9f6c8c9-xxxxx",
    "namespace_name": "guestbook",
    "labels": { "app.kubernetes.io/name": "guestbook-backend" }
  }
}
```

### 7.3 Key DaemonSet concepts shown in the chart

| Feature | Where | Why |
|---------|-------|-----|
| `hostPath` volume `/var/log` | `daemonset.yaml` | Gives the pod access to node-level log files |
| `hostPath` volume `/var/flbdb` | `daemonset.yaml` | Persists tail position DB across pod restarts |
| `tolerations: control-plane` | `values.yaml` | Allows the pod to land on tainted control-plane nodes |
| `ClusterRole` + `ClusterRoleBinding` | `rbac.yaml` | Lets Fluent Bit query the API for pod metadata |
| `updateStrategy: RollingUpdate` | `daemonset.yaml` | Replaces pods one node at a time during upgrades |

### 7.4 Remove the log collector

```bash
helm uninstall gb-logs -n guestbook
# ClusterRole and ClusterRoleBinding are also removed automatically
```

---

## Part 8 — Monitoring with Prometheus & Grafana

The `monitoring/` chart deploys the full `kube-prometheus-stack` (Prometheus + Grafana + node-exporter + kube-state-metrics). The database and frontend pods each run a metrics sidecar:

| Component | Sidecar | Port | What it exposes |
|-----------|---------|------|-----------------|
| database | `redis_exporter` | 9121 | memory, hit rate, connections, commands/sec |
| frontend | `nginx-prometheus-exporter` | 9113 | requests/sec, status codes, active connections |
| nodes | `node-exporter` (built-in) | — | CPU, RAM, disk, network |
| K8s objects | `kube-state-metrics` (built-in) | — | pod/deployment/PVC status |

Prometheus discovers the database and frontend targets automatically via `ServiceMonitor` resources in `monitoring/templates/`.

---

### 7.1 Add the Helm repository

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
```

---

### 7.2 Download chart dependencies

```bash
# Run from the examples/k8s/ directory
helm dependency update ./monitoring
```

This pulls `kube-prometheus-stack` into `monitoring/charts/`. It may take a minute on the first run.

---

### 7.3 Deploy the monitoring stack

```bash
helm install gb-monitoring ./monitoring -n monitoring --create-namespace
```

The stack takes 1–2 minutes to fully start. Watch the pods:

```bash
kubectl get pods -n monitoring --watch
```

All pods should reach `Running` or `Completed` status:

```
NAME                                                     READY   STATUS    AGE
gb-monitoring-grafana-xxxxxxxxx-xxxxx                    3/3     Running   2m
gb-monitoring-kube-prometheus-stack-operator-xxx-xxxxx   1/1     Running   2m
gb-monitoring-kube-state-metrics-xxxxxxxxx-xxxxx         1/1     Running   2m
gb-monitoring-prometheus-node-exporter-xxxxx             1/1     Running   2m
prometheus-gb-monitoring-kube-prometheus-stack-0         2/2     Running   90s
```

---

### 7.4 Open Grafana

```bash
minikube service gb-monitoring-kube-prometheus-stack-grafana -n monitoring
```

Login credentials:
- **Username:** `admin`
- **Password:** `admin`

> To change the password, set `kube-prometheus-stack.grafana.adminPassword` in `monitoring/values.yaml` before deploying.

---

### 7.5 Verify Prometheus is scraping the guestbook targets

In the Grafana sidebar go to **Connections → Data sources → Prometheus → Explore** and run:

```promql
up{namespace="guestbook"}
```

You should see two targets with value `1` (up):
- `redis-leader` — the Redis exporter
- `guestbook-frontend` — the nginx exporter

Alternatively, open the Prometheus UI directly:

```bash
kubectl port-forward -n monitoring svc/gb-monitoring-kube-prometheus-stack-prometheus 9090:9090
```

Then open `http://localhost:9090/targets` — the guestbook section should show both targets as **UP**.

---

### 7.6 Import pre-built dashboards

Grafana has a public dashboard library. Import these with **Dashboards → New → Import**, enter the ID, and select the Prometheus data source:

| Dashboard | ID | Shows |
|-----------|----|-------|
| Redis Exporter | `11835` | memory, keyspace, hit/miss rate, latency |
| NGINX Prometheus Exporter | `12708` | requests/sec, response times, status codes |
| Node Exporter Full | `1860` | CPU, RAM, disk I/O, network per node |
| Kubernetes / Pods | `6417` | pod CPU & memory per namespace |

---

### 7.7 Useful PromQL queries

```promql
# Redis memory usage in MB
redis_memory_used_bytes{namespace="guestbook"} / 1024 / 1024

# Redis commands per second
rate(redis_commands_processed_total{namespace="guestbook"}[1m])

# Nginx requests per second
rate(nginx_http_requests_total{namespace="guestbook"}[1m])

# Nginx active connections
nginx_connections_active{namespace="guestbook"}

# Pod restarts in the guestbook namespace
kube_pod_container_status_restarts_total{namespace="guestbook"}
```

---

### 7.8 Remove the monitoring stack

```bash
helm uninstall gb-monitoring -n monitoring
kubectl delete namespace monitoring
```

> **Note:** The Prometheus PersistentVolumeClaim is deleted along with the namespace. All collected metrics history will be lost.

---

## Part 9 — Self-hosted GitHub Actions Runner

The `runner/` chart deploys a **GitHub Actions self-hosted runner** inside minikube. Once running, your CI workflows can execute directly on the cluster instead of on GitHub-hosted machines — useful for testing Kubernetes-aware code or when you need custom tooling pre-installed.

The runner is based on [`myoung34/github-runner`](https://github.com/myoung34/docker-github-actions-runner) with Python 3.11 added on top (see `runner/Dockerfile`). It registers as an **ephemeral** runner: after each job it deregisters and re-registers, keeping state clean between runs.

```
GitHub Actions job
       │  triggers
       ▼
┌─────────────────────────────────┐
│  github-runner pod (minikube)   │
│  image: airis-runner:local      │
│  • python 3.11                  │
│  • github-runner agent          │
└─────────────────────────────────┘
```

---

### 9.1 Create a GitHub Personal Access Token

The runner needs a token to register itself with GitHub.

1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. Click **Generate new token (classic)**
3. Give it a name (e.g. `minikube-runner`)
4. Select scope: **`repo`** (full repository access)
5. Click **Generate token** — copy it immediately, you won't see it again

---

### 9.2 Build the runner Docker image

The runner uses a custom image (`airis-runner:local`) built from `runner/Dockerfile`.

In a multi-node minikube cluster each node has its own image store. Use `minikube image build` — it builds the image and loads it into **every node** automatically, so the pod can be scheduled anywhere without an `ImagePullBackOff`.

```bash
# Run from the examples/k8s/ directory
minikube image build -t airis-runner:local ./runner
```

This may take a few minutes on the first run while it downloads the base image.

Verify the image is present on all nodes:

```bash
minikube image ls | grep airis-runner
# docker.io/library/airis-runner:local
```

---

### 9.3 Deploy the runner chart

```bash
helm install gb-runner ./runner -n guestbook \
  --set github.accessToken="ghp_YOUR_TOKEN_HERE" \
  --set github.repoUrl="https://github.com/YOUR_USERNAME/YOUR_REPO"
```

Watch it come up:

```bash
kubectl get pods -n guestbook -l app.kubernetes.io/name=github-runner --watch
# NAME                             READY   STATUS    RESTARTS   AGE
# github-runner-xxxxxxxxx-xxxxx   1/1     Running   0          20s
```

Check the runner logs to confirm successful registration:

```bash
kubectl logs -l app.kubernetes.io/name=github-runner -n guestbook
# √ Connected to GitHub
# √ Listening for Jobs
```

---

### 9.4 Verify in the GitHub UI

1. Go to your repository on GitHub
2. Open **Settings → Actions → Runners**
3. You should see `minikube-runner` with status **Idle**

---

### 9.5 Use the runner in a workflow

Add `runs-on: self-hosted` to any job in `.github/workflows/*.yml`:

```yaml
jobs:
  test:
    runs-on: self-hosted   # ← routes this job to your minikube runner
    steps:
      - uses: actions/checkout@v4
      - run: python3 --version
      - run: kubectl get pods -n guestbook   # cluster access works too
```

Push the workflow file and trigger a run — the job will appear as **In progress** in GitHub and execute inside the minikube pod.

---

### 9.6 Scaling runners

To run multiple jobs in parallel, increase the replica count:

```bash
# Scale to 3 concurrent runners
helm upgrade gb-runner ./runner -n guestbook --set replicaCount=3

kubectl get pods -n guestbook -l app.kubernetes.io/name=github-runner
# NAME                             READY   STATUS
# github-runner-xxxxxxxxx-aaaaa   1/1     Running   ← runner 1
# github-runner-xxxxxxxxx-bbbbb   1/1     Running   ← runner 2
# github-runner-xxxxxxxxx-ccccc   1/1     Running   ← runner 3
```

If you rebuild the image after code changes, reload it into all nodes with the same command:

```bash
minikube image build -t airis-runner:local ./runner
kubectl rollout restart deployment/github-runner -n guestbook
```

---

### 9.7 Remove the runner

```bash
helm uninstall gb-runner -n guestbook
# The pod's pre-stop hook deregisters the runner from GitHub automatically
```

---

## File Structure

```
examples/k8s/
├── README.md                        ← this file
├── deploy.sh                        ← one-command deploy/remove/status script
├── database/                        ← Helm chart for Redis (StatefulSet)
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── _helpers.tpl
│       ├── statefulset.yaml         ← StatefulSet + volumeClaimTemplates
│       ├── headless-service.yaml    ← ClusterIP:None — required by StatefulSet
│       └── service.yaml             ← ClusterIP — used by backend to connect
├── backend/                         ← Helm chart for PHP API (Deployment)
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── _helpers.tpl
│       ├── deployment.yaml
│       └── service.yaml
├── frontend/                        ← Helm chart for Nginx + UI (Deployment)
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── _helpers.tpl
│       ├── configmap.yaml           ← nginx.conf + index.html
│       ├── deployment.yaml
│       ├── service.yaml
│       └── ingress.yaml
├── log-collector/                   ← Helm chart for Fluent Bit (DaemonSet)
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── _helpers.tpl
│       ├── daemonset.yaml           ← one pod per node, hostPath volumes
│       ├── configmap.yaml           ← Fluent Bit pipeline config
│       ├── serviceaccount.yaml      ← identity for RBAC
│       └── rbac.yaml                ← ClusterRole + ClusterRoleBinding
├── monitoring/                      ← Helm chart for Prometheus + Grafana
│   ├── Chart.yaml                   ← declares kube-prometheus-stack dependency
│   ├── values.yaml                  ← Prometheus/Grafana configuration
│   └── templates/
│       ├── servicemonitor-database.yaml   ← scrape redis_exporter on :9121
│       └── servicemonitor-frontend.yaml   ← scrape nginx-exporter on :9113
└── runner/                          ← Helm chart for GitHub Actions self-hosted runner
    ├── Chart.yaml
    ├── Dockerfile                   ← myoung34/github-runner + Python 3.11
    ├── values.yaml                  ← github.accessToken, github.repoUrl
    └── templates/
        ├── _helpers.tpl
        ├── deployment.yaml          ← ephemeral runner, graceful deregistration
        └── secret.yaml              ← GitHub token stored as K8s Secret
```

### When to use which workload kind

| Kind | Replicas | Identity | Storage | Typical use |
|------|----------|----------|---------|-------------|
| **Deployment** | Dynamic | Random pod names | Shared or none | Stateless apps: web servers, APIs |
| **StatefulSet** | Dynamic | Stable pod names (`pod-0`, `pod-1`) | Dedicated PVC per pod | Databases, message queues |
| **DaemonSet** | One per node | Node-pinned | `hostPath` | Agents: logging, monitoring, CNI |

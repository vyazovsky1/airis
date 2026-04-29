#!/usr/bin/env bash
# deploy.sh — deploy or remove the full Guestbook k8s demo
#
# Usage:
#   ./deploy.sh up   [-n NAMESPACE] [--monitoring]
#   ./deploy.sh down [-n NAMESPACE] [--monitoring] [--delete-pvcs]
#   ./deploy.sh status [-n NAMESPACE]

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${GREEN}[+]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
die()     { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }
section() { echo -e "\n${YELLOW}══ $* ══${NC}"; }

# ── Defaults ──────────────────────────────────────────────────────────────────
NS="guestbook"
WITH_MONITORING=false
DELETE_PVCS=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Argument parsing ──────────────────────────────────────────────────────────
CMD="${1:-help}"; shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--namespace)   NS="$2"; shift 2 ;;
    --monitoring)     WITH_MONITORING=true; shift ;;
    --delete-pvcs)    DELETE_PVCS=true; shift ;;
    *) die "Unknown option: $1" ;;
  esac
done

# ── Sanity checks ─────────────────────────────────────────────────────────────
for bin in kubectl helm; do
  command -v "$bin" &>/dev/null || die "'$bin' not found — install it first."
done

# ── Chart definitions (release-name → chart-dir : resource-kind/name) ────────
#    Order matters for 'up' (dependency first); reversed for 'down'.
declare -a RELEASES=(
  "gb-database:database:statefulset/redis-leader"
  "gb-backend:backend:deployment/guestbook-backend"
  "gb-frontend:frontend:deployment/guestbook-frontend"
  "gb-logs:log-collector:daemonset/log-collector"
)

# ── Helpers ───────────────────────────────────────────────────────────────────
wait_ready() {
  local kind_name="$1"   # e.g. deployment/guestbook-backend
  info "  Waiting for ${kind_name} …"
  kubectl rollout status "$kind_name" -n "$NS" --timeout=180s
}

# ── COMMAND: up ───────────────────────────────────────────────────────────────
cmd_up() {
  section "Deploying Guestbook to namespace '${NS}'"

  # Create namespace if it doesn't exist
  if ! kubectl get namespace "$NS" &>/dev/null; then
    info "Creating namespace '${NS}'"
    kubectl create namespace "$NS"
  else
    warn "Namespace '${NS}' already exists — skipping creation"
  fi

  for entry in "${RELEASES[@]}"; do
    IFS=':' read -r release chart resource <<< "$entry"
    section "${release}  (${chart})"

    if helm status "$release" -n "$NS" &>/dev/null; then
      warn "${release} already installed — upgrading"
      helm upgrade "$release" "${SCRIPT_DIR}/${chart}" -n "$NS"
    else
      info "Installing ${release}"
      helm install "$release" "${SCRIPT_DIR}/${chart}" -n "$NS"
    fi

    wait_ready "$resource"
    echo ""
  done

  if $WITH_MONITORING; then
    section "Monitoring  (Prometheus + Grafana)"
    if ! kubectl get namespace monitoring &>/dev/null; then
      kubectl create namespace monitoring
    fi
    if helm status gb-monitoring -n monitoring &>/dev/null; then
      warn "gb-monitoring already installed — upgrading"
      helm upgrade gb-monitoring "${SCRIPT_DIR}/monitoring" -n monitoring
    else
      info "Installing gb-monitoring"
      helm dependency update "${SCRIPT_DIR}/monitoring"
      helm install gb-monitoring "${SCRIPT_DIR}/monitoring" -n monitoring --create-namespace
    fi
    info "Monitoring pods (may take 1-2 min to fully start):"
    kubectl get pods -n monitoring
  fi

  section "Done"
  echo ""
  info "All pods:"
  kubectl get pods -n "$NS" -o wide
  echo ""
  info "Access the app:"
  echo "   minikube service guestbook-frontend -n ${NS}"
  echo "   — or —"
  echo "   kubectl port-forward service/guestbook-frontend 8080:80 -n ${NS}"
  echo "   then open http://localhost:8080"
}

# ── COMMAND: down ─────────────────────────────────────────────────────────────
cmd_down() {
  section "Removing Guestbook from namespace '${NS}'"

  # Reverse order for clean teardown
  local -a reversed=()
  for entry in "${RELEASES[@]}"; do reversed=("$entry" "${reversed[@]}"); done

  for entry in "${reversed[@]}"; do
    IFS=':' read -r release chart resource <<< "$entry"
    if helm status "$release" -n "$NS" &>/dev/null; then
      info "Uninstalling ${release}"
      helm uninstall "$release" -n "$NS"
    else
      warn "${release} not found — skipping"
    fi
  done

  if $WITH_MONITORING; then
    section "Removing monitoring"
    if helm status gb-monitoring -n monitoring &>/dev/null; then
      info "Uninstalling gb-monitoring"
      helm uninstall gb-monitoring -n monitoring
    fi
    kubectl delete namespace monitoring --ignore-not-found
  fi

  # StatefulSet PVCs are intentionally kept by Kubernetes to protect data.
  # Use --delete-pvcs to remove them explicitly.
  if $DELETE_PVCS; then
    warn "Deleting PVCs in namespace '${NS}' …"
    kubectl delete pvc --all -n "$NS" --ignore-not-found
  else
    local pvcs
    pvcs=$(kubectl get pvc -n "$NS" --no-headers 2>/dev/null | wc -l || true)
    if [[ "$pvcs" -gt 0 ]]; then
      warn "${pvcs} PVC(s) left in '${NS}' (StatefulSet data protection)."
      warn "To delete them: $0 down -n ${NS} --delete-pvcs"
    fi
  fi

  info "Deleting namespace '${NS}'"
  kubectl delete namespace "$NS" --ignore-not-found

  section "Done — cluster is clean"
}

# ── COMMAND: status ───────────────────────────────────────────────────────────
cmd_status() {
  section "Status in namespace '${NS}'"

  echo ""
  info "Helm releases:"
  helm list -n "$NS" 2>/dev/null || warn "No releases found"

  echo ""
  info "Pods:"
  kubectl get pods -n "$NS" -o wide 2>/dev/null || warn "No pods"

  echo ""
  info "Services:"
  kubectl get services -n "$NS" 2>/dev/null || warn "No services"

  echo ""
  info "PersistentVolumeClaims:"
  kubectl get pvc -n "$NS" 2>/dev/null || warn "No PVCs"

  if $WITH_MONITORING; then
    echo ""
    info "Monitoring pods:"
    kubectl get pods -n monitoring -o wide 2>/dev/null || warn "No monitoring pods"
  fi
}

# ── Dispatch ──────────────────────────────────────────────────────────────────
case "$CMD" in
  up)     cmd_up ;;
  down)   cmd_down ;;
  status) cmd_status ;;
  *)
    echo "Usage:"
    echo "  $(basename "$0") up     [-n NAMESPACE] [--monitoring]"
    echo "  $(basename "$0") down   [-n NAMESPACE] [--monitoring] [--delete-pvcs]"
    echo "  $(basename "$0") status [-n NAMESPACE] [--monitoring]"
    echo ""
    echo "Examples:"
    echo "  ./deploy.sh up                          # deploy to 'guestbook' namespace"
    echo "  ./deploy.sh up --monitoring             # deploy app + Prometheus/Grafana"
    echo "  ./deploy.sh down --delete-pvcs          # remove everything incl. PVCs"
    echo "  ./deploy.sh status"
    exit 1
    ;;
esac

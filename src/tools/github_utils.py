import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AIRIS-Github")

def get_pull_request_diff(pr_number: int, workload_name: str = "") -> str:
    """Simulates fetching a PR diff and extracting manifest changes."""
    # We simulate a PR diff that is bumping something up or claiming heavy storage
    if pr_number == 101:
        if "back-end" in workload_name:
            # Scenario: backend is asking for more resources (from 250m/256Mi to 1500m/4Gi)
            return '''
diff --git a/examples/back-end/deployment.yaml b/examples/back-end/deployment.yaml
--- a/examples/back-end/deployment.yaml
+++ b/examples/back-end/deployment.yaml
@@ -23,8 +23,8 @@
         resources:
           requests:
-            cpu: "250m"
-            memory: "256Mi"
+            cpu: "1500m"
+            memory: "4Gi"
           limits:
             cpu: "1000m"
             memory: "1Gi"
         '''
        elif "front-end" in workload_name:
            # Scenario: frontend is asking for 3 replicas and more memory
            return '''
diff --git a/examples/front-end/deployment.yaml b/examples/front-end/deployment.yaml
--- a/examples/front-end/deployment.yaml
+++ b/examples/front-end/deployment.yaml
@@ -8,7 +8,7 @@
-  replicas: 1
+  replicas: 3
...
         resources:
           requests:
-            cpu: "100m"
-            memory: "512Mi"
+            cpu: "500m"
+            memory: "2Gi"
         '''
        else:
            # Default fall-back scenario (e.g. payments-db legacy)
            return '''
diff --git a/kubernetes/production/payments-db/statefulset.yaml b/kubernetes/production/payments-db/statefulset.yaml
--- a/kubernetes/production/payments-db/statefulset.yaml
+++ b/kubernetes/production/payments-db/statefulset.yaml
@@ -40,7 +40,7 @@
   volumeClaimTemplates:
   - metadata:
       name: data
     spec:
       resources:
         requests:
-          storage: 100Gi
+          storage: 200Gi
         '''
    return "No significant changes."

def create_pull_request_review(pr_number: int, comment_markdown: str):
    """Simulates posting the final AIRIS decision block to standard output."""
    logger.info(f"--- POSTING TO GITHUB PR #{pr_number} ---")
    print("\n" + "="*50)
    print(comment_markdown)
    print("="*50 + "\n")

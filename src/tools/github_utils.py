import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AIRIS-Github")

def get_pull_request_diff(pr_number: int) -> str:
    """Simulates fetching a PR diff and extracting manifest changes."""
    # We simulate a PR diff that is bumping something up or claiming heavy storage
    if pr_number == 101:
        # Scenario: payments-db is asking for 200Gi PVC
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

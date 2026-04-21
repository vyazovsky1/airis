# ToDo

The following items have been deferred from the initial solution design scope and must be addressed before or during the production implementation phase:

- **Security & RBAC Considerations**: Define the minimum cluster permissions required for the agent in the CI/CD integration. The agent typically requires read-only access to `pods`, `persistentvolumeclaims`, `nodes/stats`, and `metrics.k8s.io` to function. A dedicated ServiceAccount policy should be designed.
- **LLM Context Constraints (Large PR Diffs)**: Implement a strategy to handle massive PR diffs in `get_pr_manifest_diff`. E.g., limit the payload size or number of files processed so it does not blow up the LLM string length limit.
-- **Smart Cache**: Persist target applications intention and recommendations made about its infrastructure


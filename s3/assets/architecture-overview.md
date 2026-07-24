# Architecture Overview

```text
CLI / Examples
    |
    v
Configuration -> Session Factory -> boto3 clients
    |                              |
    v                              v
Validated settings          S3, STS, IAM APIs
    |
    v
Reusable managers:
  - buckets
  - objects
  - security
  - lifecycle
  - data lake utilities
```

The design keeps authentication, configuration, and AWS clients separate from
feature-specific managers. That makes examples easier to test with moto or
botocore Stubber and easier to adapt for production tools.
# Boto3 — Session Management

## Service Overview

A **Boto3 Session** stores configuration state — credentials, region, and profile — and is the factory for clients and resources. Proper session management ensures consistent configuration across multi-region data pipelines.

**Key concepts:**
- **Session** — configuration container (credentials, region, profile)
- **Client** — low-level service API (recommended for most data engineering tasks)
- **Resource** — higher-level object-oriented interface (S3, DynamoDB, EC2)

**When to use sessions:** Create one session per process/worker; reuse clients derived from it for connection pooling and credential caching.

---

## AWS CLI Commands

Sessions in Boto3 mirror CLI profile configuration:

```bash
# CLI equivalent of boto3.Session(profile_name="data-engineer")
export AWS_PROFILE=data-engineer
export AWS_DEFAULT_REGION=us-east-1
aws sts get-caller-identity
```

List configured profiles:

```bash
aws configure list-profiles
```

Show resolved config for a profile:

```bash
aws configure list --profile data-engineer
```

---

## Advanced Commands

### Multi-Region CLI Sessions

```bash
aws s3 ls --region eu-west-1 --profile data-engineer
aws glue get-databases --region us-west-2 --profile data-engineer
```

### Profile with Default Output and Region

`~/.aws/config`:

```ini
[profile data-engineer]
region = us-east-1
output = json
max_attempts = 10
retry_mode = adaptive
```

---

## Python Boto3 Examples

### Default Session

```python
import boto3

session = boto3.Session()
print(session.region_name)
print(session.get_credentials().method)  # e.g., 'iam-role', 'sso', 'env'
```

### Explicit Profile and Region

```python
session = boto3.Session(
    profile_name="data-engineer",
    region_name="us-east-1",
)
s3 = session.client("s3")
glue = session.client("glue")
```

### Multi-Region Clients from One Session

```python
session = boto3.Session(profile_name="data-engineer")

def client_for_region(service: str, region: str):
    return session.client(service, region_name=region)

s3_east = client_for_region("s3", "us-east-1")
s3_west = client_for_region("s3", "us-west-2")
```

### Session with Botocore Config

```python
import boto3
from botocore.config import Config

config = Config(
    region_name="us-east-1",
    retries={"max_attempts": 10, "mode": "adaptive"},
    connect_timeout=5,
    read_timeout=60,
    max_pool_connections=50,
)

session = boto3.Session(profile_name="data-engineer")
s3 = session.client("s3", config=config)
```

### Resource vs Client

```python
session = boto3.Session(region_name="us-east-1")

# Client — full API, recommended for pipelines
s3_client = session.client("s3")
s3_client.put_object(Bucket="my-bucket", Key="data/file.parquet", Body=b"...")

# Resource — convenient for bucket/object iteration
s3_resource = session.resource("s3")
for obj in s3_resource.Bucket("my-bucket").objects.filter(Prefix="orders/"):
    print(obj.key)
```

### Thread-Safe Pattern for Workers

```python
import threading

_local = threading.local()


def get_session() -> "boto3.Session":
    if not hasattr(_local, "session"):
        _local.session = boto3.Session(profile_name="data-engineer")
    return _local.session


def get_s3_client():
    if not hasattr(_local, "s3"):
        _local.s3 = get_session().client("s3")
    return _local.s3
```

### Singleton Session for Long-Running ETL

```python
import boto3
from functools import lru_cache


@lru_cache(maxsize=1)
def get_boto3_session(profile: str = "data-engineer", region: str = "us-east-1") -> boto3.Session:
    return boto3.Session(profile_name=profile, region_name=region)


def get_client(service: str, profile: str = "data-engineer", region: str = "us-east-1"):
    return get_boto3_session(profile, region).client(service)
```

---

## Security Considerations

- Do not share sessions across untrusted code boundaries — credentials are attached to the session.
- Clear cached sessions when rotating credentials in long-running daemons.
- Use separate profiles for prod vs non-prod to prevent accidental cross-environment access.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Client uses wrong region | Pass `region_name` explicitly — session default may be `None` |
| `ProfileNotFound` | Run `aws configure list-profiles`; verify profile name spelling |
| Stale credentials in long process | Use refreshable credentials or recreate session after SSO expiry |
| Connection pool exhausted | Increase `max_pool_connections` in `Config` |

---

## Best Practices

- **One session per process** — create clients from it, don't create new sessions per API call.
- **Pass region explicitly** for multi-region pipelines — don't rely on implicit defaults.
- **Use clients over resources** for Glue, Athena, Step Functions, and Lake Formation.
- **Configure retries and timeouts** at session/client creation, not per call.
- **Inject sessions in tests** — pass mock sessions/clients for unit testing.
- **Log session identity** at startup via `sts.get_caller_identity()`.

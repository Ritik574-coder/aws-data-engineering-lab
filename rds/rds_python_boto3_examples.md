# RDS — Python Boto3 Examples

```python
import boto3
from botocore.exceptions import ClientError

rds = boto3.client("rds")

def create_snapshot(db_id: str, snap_id: str) -> str:
    try:
        resp = rds.create_db_snapshot(
            DBSnapshotIdentifier=snap_id,
            DBInstanceIdentifier=db_id,
        )
        return resp["DBSnapshot"]["DBSnapshotIdentifier"]
    except ClientError:
        raise
```

---

## Best Practices

- Use **paginators** for `describe_db_snapshots`.
- Tag snapshots with `RetentionDays` for lifecycle automation.

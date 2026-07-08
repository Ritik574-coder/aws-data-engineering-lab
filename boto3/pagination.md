# Boto3 — Pagination

## Service Overview

Many AWS APIs return paginated results — a subset of items plus a continuation token. Boto3 **paginators** automate fetching all pages, preventing missed data in list operations across large data platform resources.

**Common paginated operations:**
- `s3.list_objects_v2` — data lake object inventory
- `glue.get_tables` — catalog enumeration
- `iam.list_users` — identity audits
- `stepfunctions.list_executions` — pipeline run history

**When to use paginators:** Always prefer paginators over manual `NextToken` loops for list operations.

---

## AWS CLI Commands

The AWS CLI v2 paginates automatically but supports manual control:

```bash
# CLI auto-paginates; limit page size
aws s3api list-objects-v2 --bucket my-data-lake-raw --prefix orders/ --max-items 100

# Get next page
aws s3api list-objects-v2 --bucket my-data-lake-raw --starting-token <NextToken>
```

Disable pagination (single page only):

```bash
aws s3api list-objects-v2 --bucket my-bucket --no-paginate
```

---

## Advanced Commands

### JMESPath on Paginated Results

```bash
aws glue get-tables --database-name analytics_curated \
  --query 'TableList[*].Name' --output text
```

### Page Size Tuning

```bash
aws ec2 describe-instances --page-size 50 --max-items 200
```

---

## Python Boto3 Examples

### Basic Paginator

```python
import boto3

s3 = boto3.client("s3")
paginator = s3.get_paginator("list_objects_v2")

for page in paginator.paginate(Bucket="my-data-lake-raw", Prefix="orders/"):
    for obj in page.get("Contents", []):
        print(obj["Key"], obj["Size"])
```

### Paginator with Page Size

```python
paginator = s3.get_paginator("list_objects_v2")
page_iterator = paginator.paginate(
    Bucket="my-data-lake-raw",
    Prefix="orders/",
    PaginationConfig={"PageSize": 1000, "MaxItems": 10000},
)

for page in page_iterator:
    print(f"Page with {len(page.get('Contents', []))} objects")
```

### Collect All Glue Tables

```python
def list_all_tables(glue_client, database: str) -> list[str]:
    paginator = glue_client.get_paginator("get_tables")
    names = []
    for page in paginator.paginate(DatabaseName=database):
        names.extend(t["Name"] for t in page["TableList"])
    return names
```

### Filter Pages with Iterator

```python
paginator = s3.get_paginator("list_objects_v2")
page_iterator = paginator.paginate(Bucket="my-bucket", Prefix="logs/")

filtered = page_iterator.search("Contents[?Size > `1048576`].[Key, Size]")
for key, size in filtered:
    print(key, size)
```

### Manual Pagination (When Paginator Unavailable)

```python
def list_all_executions(sfn_client, state_machine_arn: str) -> list[dict]:
    executions = []
    next_token = None

    while True:
        kwargs = {"stateMachineArn": state_machine_arn, "maxResults": 100}
        if next_token:
            kwargs["nextToken"] = next_token

        response = sfn_client.list_executions(**kwargs)
        executions.extend(response["executions"])

        next_token = response.get("nextToken")
        if not next_token:
            break

    return executions
```

### Production — Paginate with Early Exit

```python
def find_latest_object(s3_client, bucket: str, prefix: str) -> dict | None:
    paginator = s3_client.get_paginator("list_objects_v2")
    latest = None

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if latest is None or obj["LastModified"] > latest["LastModified"]:
                latest = obj

    return latest
```

### List Available Paginators

```python
s3 = boto3.client("s3")
print(s3.can_paginate("list_objects_v2"))  # True
print([p for p in s3.paginator.PAGINATORS])  # all paginator names
```

---

## Security Considerations

- Paginating through large buckets can be slow and costly — scope with tight prefixes.
- Listing IAM resources requires broad read permissions — audit who runs enumeration scripts.
- Avoid logging full page contents — may include sensitive object keys or ARNs.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Missing items in results | Not using paginator — some APIs truncate at 1000 items |
| `PaginationConfig MaxItems` stops early | Intentional limit — remove or increase MaxItems |
| Slow S3 listing | Use S3 Inventory or Athena over inventory reports for large buckets |
| Empty pages | Normal for some APIs — check `Contents` key exists |
| `OperationNotPageable` | Use manual NextToken loop or upgrade boto3 |

---

## Best Practices

- **Always use paginators** for list operations in production code.
- Set **`PageSize`** appropriately — larger pages reduce API calls but increase memory.
- Use **`search()`** for client-side JMESPath filtering on pages.
- For massive S3 buckets, prefer **S3 Inventory** or **Glob patterns** with known partition structure.
- Handle empty result sets — `Contents` may be absent from the page dict.
- Cache paginator objects — `get_paginator()` is cheap but reusable.

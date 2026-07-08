# DynamoDB — Operations

## Service Overview

**Amazon DynamoDB** is a fully managed, serverless NoSQL key-value and document database designed for single-digit millisecond performance at any scale. It is widely used in data engineering for operational data stores, real-time aggregations, change data capture (CDC) sources, and low-latency serving layers.

**Common use cases:**
- Real-time event ingestion and session state (clickstreams, IoT telemetry)
- CDC source via DynamoDB Streams → Lambda → S3/Kinesis
- Feature stores and lookup tables for ML pipelines
- Metadata catalogs and job state tracking for ETL orchestration
- High-throughput counters and aggregations with atomic updates

**When to use it:** When you need predictable low-latency reads/writes at scale without managing servers, with optional global replication (Global Tables) and tight integration with Lambda, Kinesis, and Glue.

**Key concepts for data engineers:**
| Concept | Description |
|---------|-------------|
| **Partition key** | Hash key that determines item distribution |
| **Sort key** | Optional range key for composite access patterns |
| **GSI / LSI** | Secondary indexes for alternate query paths |
| **Streams** | Ordered change log (NEW_AND_OLD_IMAGES) for CDC |
| **On-demand vs provisioned** | Pay per request vs reserved RCU/WCU |
| **TTL** | Automatic expiry for staging/temp data |

---

## AWS CLI Commands

### List Tables

**Purpose:** Enumerate DynamoDB tables in the account/region.

**Command:**

```bash
aws dynamodb list-tables --output table
```

**Example Output:**

```
--------------------------
|       ListTables       |
+------------------------+
|  analytics-job-state   |
|  pipeline-metadata     |
|  user-events-prod      |
+------------------------+
```

**Required IAM:** `dynamodb:ListTables`

---

### Describe Table

**Purpose:** Inspect schema, throughput, indexes, and stream configuration.

**Command:**

```bash
aws dynamodb describe-table \
  --table-name user-events-prod \
  --query 'Table.{Name:TableName,Status:TableStatus,Keys:KeySchema,Items:ItemCount,SizeBytes:TableSizeBytes,Stream:LatestStreamArn,Billing:BillingModeSummary.BillingMode}' \
  --output table
```

**Parameters:**
| Parameter | Description |
|-----------|-------------|
| `--table-name` | Target table name |
| `--query` | JMESPath filter for output |

---

### Create Table (Provisioned Throughput)

**Purpose:** Create a table with explicit RCU/WCU for predictable workloads.

**Command:**

```bash
aws dynamodb create-table \
  --table-name pipeline-metadata \
  --attribute-definitions \
    AttributeName=job_id,AttributeType=S \
    AttributeName=run_date,AttributeType=S \
  --key-schema \
    AttributeName=job_id,KeyType=HASH \
    AttributeName=run_date,KeyType=RANGE \
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
  --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES \
  --tags Key=Environment,Value=prod Key=Team,Value=data-platform
```

**Example Output:**

```json
{
    "TableDescription": {
        "TableName": "pipeline-metadata",
        "TableStatus": "CREATING",
        "LatestStreamArn": "arn:aws:dynamodb:us-east-1:123456789012:table/pipeline-metadata/stream/2025-03-01T12:00:00.000"
    }
}
```

---

### Create Table (On-Demand)

**Purpose:** Serverless billing mode for spiky or unknown traffic patterns.

**Command:**

```bash
aws dynamodb create-table \
  --table-name analytics-job-state \
  --attribute-definitions AttributeName=job_id,AttributeType=S \
  --key-schema AttributeName=job_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

---

### Put Item

**Purpose:** Insert or overwrite a single item (common for job checkpoints).

**Command:**

```bash
aws dynamodb put-item \
  --table-name pipeline-metadata \
  --item '{
    "job_id": {"S": "orders-daily-etl"},
    "run_date": {"S": "2025-03-01"},
    "status": {"S": "SUCCESS"},
    "rows_processed": {"N": "1250000"},
    "updated_at": {"S": "2025-03-01T06:15:00Z"}
  }'
```

---

### Get Item

**Purpose:** Point read by primary key.

**Command:**

```bash
aws dynamodb get-item \
  --table-name pipeline-metadata \
  --key '{"job_id":{"S":"orders-daily-etl"},"run_date":{"S":"2025-03-01"}}' \
  --consistent-read \
  --output json
```

**Parameters:**
| Flag | Description |
|------|-------------|
| `--consistent-read` | Strongly consistent read (2x RCU cost on provisioned tables) |
| `--projection-expression` | Return subset of attributes |

---

### Query

**Purpose:** Efficient range queries on partition key (preferred over Scan).

**Command:**

```bash
aws dynamodb query \
  --table-name pipeline-metadata \
  --key-condition-expression "job_id = :jid AND run_date BETWEEN :start AND :end" \
  --expression-attribute-values '{
    ":jid": {"S": "orders-daily-etl"},
    ":start": {"S": "2025-03-01"},
    ":end": {"S": "2025-03-07"}
  }' \
  --scan-index-forward false \
  --limit 100
```

---

### Scan (Use Sparingly)

**Purpose:** Full table read — acceptable for small tables or one-off exports; avoid on large production tables.

**Command:**

```bash
aws dynamodb scan \
  --table-name analytics-job-state \
  --filter-expression "#s = :failed" \
  --expression-attribute-names '{"#s":"status"}' \
  --expression-attribute-values '{":failed":{"S":"FAILED"}}' \
  --max-items 50
```

---

### Batch Write Items

**Purpose:** Bulk ingest up to 25 items per request.

**Command:**

```bash
aws dynamodb batch-write-item \
  --request-items '{
    "user-events-prod": [
      {"PutRequest": {"Item": {"event_id":{"S":"e1"},"user_id":{"S":"u100"},"event_type":{"S":"purchase"}}}},
      {"PutRequest": {"Item": {"event_id":{"S":"e2"},"user_id":{"S":"u101"},"event_type":{"S":"view"}}}}
    ]
  }'
```

---

### Update Table Throughput

**Purpose:** Scale provisioned capacity or switch billing mode.

**Command:**

```bash
aws dynamodb update-table \
  --table-name pipeline-metadata \
  --provisioned-throughput ReadCapacityUnits=20,WriteCapacityUnits=10
```

---

### Enable TTL

**Purpose:** Auto-expire staging records (e.g., temp ETL locks).

**Command:**

```bash
aws dynamodb update-time-to-live \
  --table-name etl-staging-locks \
  --time-to-live-specification Enabled=true,AttributeName=expires_at
```

---

### Export Table to S3

**Purpose:** Point-in-time export to S3 for analytics (Athena, Spark, Redshift Spectrum).

**Command:**

```bash
aws dynamodb export-table-to-point-in-time \
  --table-arn arn:aws:dynamodb:us-east-1:123456789012:table/user-events-prod \
  --s3-bucket my-data-lake-raw \
  --s3-prefix dynamodb-exports/user-events-prod/2025-03-01/ \
  --export-format DYNAMODB_JSON
```

---

### Delete Table

**Purpose:** Remove table and all data (irreversible).

**Command:**

```bash
aws dynamodb delete-table --table-name etl-staging-locks-dev
```

---

## Advanced Commands

### Create Global Secondary Index (GSI)

```bash
aws dynamodb update-table \
  --table-name user-events-prod \
  --attribute-definitions AttributeName=event_type,AttributeType=S AttributeName=event_ts,AttributeType=S \
  --global-secondary-index-updates '[
    {
      "Create": {
        "IndexName": "event_type-ts-index",
        "KeySchema": [
          {"AttributeName": "event_type", "KeyType": "HASH"},
          {"AttributeName": "event_ts", "KeyType": "RANGE"}
        ],
        "Projection": {"ProjectionType": "ALL"},
        "ProvisionedThroughput": {"ReadCapacityUnits": 10, "WriteCapacityUnits": 10}
      }
    }
  ]'
```

### Paginated Scan with `--starting-token`

```bash
aws dynamodb scan \
  --table-name user-events-prod \
  --max-items 1000 \
  --starting-token "eyJ..."
```

### Describe Stream and Get Shard Iterator

```bash
STREAM_ARN=$(aws dynamodb describe-table \
  --table-name pipeline-metadata \
  --query 'Table.LatestStreamArn' --output text)

aws dynamodbstreams describe-stream --stream-arn "$STREAM_ARN"

SHARD_ID=$(aws dynamodbstreams describe-stream \
  --stream-arn "$STREAM_ARN" \
  --query 'StreamDescription.Shards[0].ShardId' --output text)

ITERATOR=$(aws dynamodbstreams get-shard-iterator \
  --stream-arn "$STREAM_ARN" \
  --shard-id "$SHARD_ID" \
  --shard-iterator-type TRIM_HORIZON \
  --query 'ShardIterator' --output text)

aws dynamodbstreams get-records --shard-iterator "$ITERATOR"
```

### PartiQL — SQL-Like Queries

```bash
aws dynamodb execute-statement \
  --statement 'SELECT job_id, run_date, status FROM "pipeline-metadata" WHERE job_id = ?' \
  --parameters '[{"S":"orders-daily-etl"}]'
```

### Batch Get Items

```bash
aws dynamodb batch-get-item \
  --request-items '{
    "pipeline-metadata": {
      "Keys": [
        {"job_id":{"S":"orders-daily-etl"},"run_date":{"S":"2025-03-01"}},
        {"job_id":{"S":"orders-daily-etl"},"run_date":{"S":"2025-03-02"}}
      ]
    }
  }'
```

### Enable Point-in-Time Recovery (PITR)

```bash
aws dynamodb update-continuous-backups \
  --table-name user-events-prod \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true
```

### Filter Tables with JMESPath

```bash
aws dynamodb list-tables \
  --query 'TableNames[?contains(@, `prod`)]' \
  --output text
```

---

## Python (Boto3) Examples

### Basic — Query by Partition Key

```python
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("pipeline-metadata")

response = table.query(
    KeyConditionExpression="job_id = :jid",
    ExpressionAttributeValues={":jid": "orders-daily-etl"},
)
for item in response["Items"]:
    print(item["run_date"], item["status"])
```

### Production-Ready — Batch Writer with Retry

```python
import logging
from typing import Iterable

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def batch_write_items(table_name: str, items: Iterable[dict]) -> None:
    table = boto3.resource("dynamodb").Table(table_name)
    with table.batch_writer(overwrite_by_pkeys=["job_id", "run_date"]) as batch:
        for item in items:
            batch.put_item(Item=item)
    logger.info("Wrote %d items to %s", len(list(items)), table_name)
```

See [dynamodb_python_examples.md](dynamodb_python_examples.md) for streams, exports, and paginator patterns.

---

## Security Considerations

- Enable **encryption at rest** (AWS owned key by default; use **CMK via KMS** for audit and cross-account access).
- Apply **least-privilege IAM** scoped to table ARNs: `dynamodb:Query`, `dynamodb:PutItem`, etc.
- Use **VPC endpoints** (Gateway) for private access from EMR/Glue without internet egress.
- Enable **CloudTrail** data events for sensitive tables to audit API calls.
- Restrict **Scan** permissions in production; prefer Query/GSI for pipeline reads.
- Use **resource-based policies** and **IAM condition keys** (`dynamodb:LeadingKeys`) for multi-tenant isolation.

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `ProvisionedThroughputExceededException` | Hot partition or insufficient WCU/RCU | Enable auto scaling; redesign partition key; switch to on-demand |
| `ValidationException: One or more parameter values were invalid` | Wrong attribute types or missing index keys | Verify KeySchema matches item attributes |
| `ResourceNotFoundException` | Wrong region or deleted table | Confirm table name and region in CLI profile |
| Slow Scan on large table | Full table read | Use Query, GSI, or Export to S3 instead |
| Stream records missing | Stream disabled or wrong view type | Enable stream with `NEW_AND_OLD_IMAGES` before CDC |
| `AccessDeniedException` | Missing IAM on table/index ARN | Include index ARNs in policy for GSI queries |

---

## Best Practices

- **Design access patterns first** — partition key should distribute writes evenly (avoid monotonic keys like timestamps alone).
- Use **composite keys** (`job_id` + `run_date`) for time-series pipeline metadata.
- Prefer **on-demand** for dev/spiky workloads; use **auto scaling** for steady provisioned tables.
- Enable **DynamoDB Streams** for CDC into S3 (via Lambda/Firehose) rather than polling with Scan.
- Use **Export to S3** for bulk analytics instead of Scan + custom export scripts.
- Set **TTL** on ephemeral data (locks, cache rows) to reduce storage cost.
- Tag tables (`Environment`, `DataDomain`, `CostCenter`) for chargeback.
- Monitor **ConsumedReadCapacityUnits**, **ThrottledRequests**, and **SuccessfulRequestLatency** in CloudWatch.
- For Glue/Spark reads, use the **DynamoDB connector** or exported S3 data in Parquet format.

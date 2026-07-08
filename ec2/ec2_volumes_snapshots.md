# EC2 — Volumes & Snapshots

## Service Overview

EBS volumes provide persistent block storage for EC2. Snapshots enable backup and AMI creation for ETL worker images.

---

## AWS CLI Commands

### Create Volume

```bash
aws ec2 create-volume \
  --availability-zone us-east-1a \
  --size 500 \
  --volume-type gp3 \
  --encrypted \
  --tag-specifications 'ResourceType=volume,Tags=[{Key=Name,Value=spark-data-vol}]'
```

### Attach Volume

```bash
aws ec2 attach-volume \
  --volume-id vol-0abc123 \
  --instance-id i-0def456 \
  --device /dev/sdf
```

### Create Snapshot

```bash
aws ec2 create-snapshot \
  --volume-id vol-0abc123 \
  --description "Pre-upgrade snapshot for ETL worker" \
  --tag-specifications 'ResourceType=snapshot,Tags=[{Key=Name,Value=etl-worker-snap}]'
```

### List Snapshots

```bash
aws ec2 describe-snapshots --owner-ids self \
  --query 'Snapshots[?StartTime>=`2025-01-01`].{ID:SnapshotId,Size:VolumeSize,Start:StartTime}' \
  --output table
```

---

## Advanced Commands

### Copy Snapshot Cross-Region

```bash
aws ec2 copy-snapshot \
  --source-region us-east-1 \
  --source-snapshot-id snap-0abc123 \
  --destination-region us-west-2 \
  --description "DR copy"
```

---

## Python (Boto3) Examples

```python
import boto3

ec2 = boto3.client("ec2")

def snapshot_volume(volume_id: str, description: str) -> str:
    snap = ec2.create_snapshot(VolumeId=volume_id, Description=description)
    ec2.get_waiter("snapshot_completed").wait(SnapshotIds=[snap["SnapshotId"]])
    return snap["SnapshotId"]
```

---

## Security Considerations

- Enable **encryption by default** at account level.
- Restrict snapshot sharing; use **AWS Backup** for centralized policies.
- Share snapshots only with specific account IDs, never publicly.

---

## Best Practices

- Use **gp3** for cost-effective general-purpose workloads.
- Automate snapshot lifecycle with **DLM (Data Lifecycle Manager)**.
- Size volumes for IOPS requirements; monitor `VolumeQueueLength`.

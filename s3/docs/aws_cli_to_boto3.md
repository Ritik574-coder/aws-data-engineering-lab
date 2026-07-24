# AWS CLI to boto3 Translation

This document teaches how common AWS CLI S3 commands map to boto3.

| AWS CLI | boto3 Pattern |
| --- | --- |
| `aws s3 ls` | `list_buckets` or `list_objects_v2` paginator |
| `aws s3 cp local s3://bucket/key` | `upload_file` |
| `aws s3 cp s3://bucket/key local` | `download_file` |
| `aws s3 mv` | `copy_object` followed by `delete_object` |
| `aws s3 rm` | `delete_object` or `delete_objects` |
| `aws s3 sync` | paginated listing plus comparison and transfer logic |
| `aws s3 presign` | `generate_presigned_url` |
| `aws s3api put-bucket-versioning` | `put_bucket_versioning` |
| `aws s3api put-bucket-lifecycle-configuration` | `put_bucket_lifecycle_configuration` |

High-level `aws s3` commands often perform multiple API calls. boto3 code should
make pagination, retries, dry-run behavior, metadata handling, and destructive
actions explicit.


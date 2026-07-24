# Amazon S3 Operations Reference

This guide maps major S3 concepts to boto3 implementation patterns in this
repository.

## Bucket Management

Buckets are regional containers with globally unique names. You can create,
delete, list, inspect, tag, encrypt, and secure buckets. Buckets cannot be
renamed; the production rename strategy is create a new bucket, copy data,
validate, update clients, and then decommission the old bucket.

Use `S3BucketManager` for create, delete, empty, existence, region, list, and
statistics workflows.

## Object Operations

Objects are addressed by bucket and key. S3 does not have real directories.
Upload, download, copy, move, rename, replace, restore, bulk transfer, recursive
transfer, and sync workflows are built from object APIs.

Use `S3ObjectManager` for uploads, downloads, metadata, tags, copy, move,
delete, prefix listing, folder markers, and presigned URLs.

## Prefixes and Folders

Prefixes are key naming patterns. A key such as
`bronze/orders/year=2026/month=07/file.parquet` is one object key, not a nested
directory tree. Folder marker objects are zero-byte objects ending in `/` and
exist mainly for console compatibility.

## Metadata

Object metadata is useful for small immutable descriptors. Updating metadata
requires copying the object with `MetadataDirective=REPLACE`. User metadata is
not a searchable catalog and should not replace Glue Data Catalog, DynamoDB, or
inventory-driven indexing.

## Tags

Tags are key-value labels used for cost allocation, lifecycle filtering, access
decisions, and governance. Tags are separate from metadata and have their own
APIs.

## Versioning

Versioning protects against overwrites and deletes. Delete operations create
delete markers unless a specific version is deleted. Versioned buckets require
noncurrent version cleanup to control cost.

## Lifecycle

Lifecycle rules transition or expire objects asynchronously. They can filter by
prefix, tag, or object size. They are powerful but destructive when expiration
is enabled.

## Storage Classes

Storage classes optimize different cost and access patterns. Choose based on
total cost: storage, requests, retrieval, monitoring, minimum duration, and
operational complexity.

## Encryption

SSE-S3 is simple. SSE-KMS adds key-level control and auditability. SSE-C makes
the application responsible for customer-provided keys. Client-side encryption
moves encryption before data reaches S3.

## Security

Modern S3 security should prefer IAM policies, bucket policies, Block Public
Access, Object Ownership, TLS-only policies, KMS enforcement, and explicit
deny statements for mandatory rules.

## Presigned URLs

Presigned URLs delegate time-limited access using the signer principal's
permissions. Validate keys before signing and keep expirations short.

## Multipart Upload

Multipart upload improves large object reliability and throughput. Incomplete
multipart uploads cost money until completed, aborted, or cleaned by lifecycle.

## Replication

Replication is asynchronous and requires versioning. Cross-Region Replication
supports resilience and compliance. Same-Region Replication supports same-region
copies for ownership, compliance, or processing boundaries.

## Events

S3 can publish events to SNS, SQS, Lambda, and EventBridge. Consumers must be
idempotent because delivery is at least once and ordering is not guaranteed.

## Logging and Monitoring

Use server access logs for access records, CloudTrail data events for audited
object API activity, CloudWatch metrics for operational alarms, Inventory for
object estate reporting, and Storage Lens for organization-level visibility.

## Advanced Features

Object Lock supports retention and legal holds. Access Points simplify
application-specific access. VPC endpoints keep traffic private. Requester Pays
shifts request and transfer charges. Batch Operations applies actions at massive
scale. S3 Select filters object contents server-side for supported formats.


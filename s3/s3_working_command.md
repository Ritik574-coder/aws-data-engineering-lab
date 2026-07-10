# AWS S3 Complete Guide — Terminal (CLI) + Python (boto3)

A single reference covering AWS S3 setup, all common CLI commands (Linux), and Python (boto3) code for buckets and objects.

---

## 1. Setup & Configuration

### 1.1 Install AWS CLI (Linux)
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
aws --version
```

### 1.2 Configure credentials
```bash
aws configure
# Prompts for:
# AWS Access Key ID
# AWS Secret Access Key
# Default region name (e.g., ap-south-1)
# Default output format (json/text/table)
```

Multiple profiles:
```bash
aws configure --profile myprofile
aws s3 ls --profile myprofile
```

Credentials file locations: `~/.aws/credentials` and `~/.aws/config`

### 1.3 Install boto3 (Python)
```bash
pip install boto3 --break-system-packages
```

Configure via environment variables (alternative to `aws configure`):
```bash
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
export AWS_DEFAULT_REGION="ap-south-1"
```

---

## 2. AWS CLI — S3 Commands (`aws s3`)

The `aws s3` command set is high-level (good for everyday file operations).

### 2.1 Bucket operations
```bash
# List all buckets
aws s3 ls

# Create a bucket
aws s3 mb s3://my-bucket-name

# Create a bucket in a specific region
aws s3 mb s3://my-bucket-name --region ap-south-1

# Delete an empty bucket
aws s3 rb s3://my-bucket-name

# Delete a bucket AND all objects inside it
aws s3 rb s3://my-bucket-name --force
```

### 2.2 Listing objects
```bash
# List objects/folders in a bucket
aws s3 ls s3://my-bucket-name

# List recursively (all nested objects)
aws s3 ls s3://my-bucket-name --recursive

# List with human-readable sizes and summarize
aws s3 ls s3://my-bucket-name --recursive --human-readable --summarize

# List a specific "folder" prefix
aws s3 ls s3://my-bucket-name/folder/
```

### 2.3 Uploading files
```bash
# Upload a single file
aws s3 cp localfile.txt s3://my-bucket-name/

# Upload with a different key/name
aws s3 cp localfile.txt s3://my-bucket-name/renamed.txt

# Upload an entire directory recursively
aws s3 cp ./local-folder s3://my-bucket-name/folder/ --recursive

# Upload with storage class
aws s3 cp localfile.txt s3://my-bucket-name/ --storage-class STANDARD_IA

# Upload with server-side encryption
aws s3 cp localfile.txt s3://my-bucket-name/ --sse AES256
```

### 2.4 Downloading files
```bash
# Download a single file
aws s3 cp s3://my-bucket-name/file.txt ./localfile.txt

# Download an entire folder
aws s3 cp s3://my-bucket-name/folder/ ./local-folder --recursive
```

### 2.5 Sync (mirror directories/buckets)
```bash
# Sync local folder -> bucket (uploads new/changed files only)
aws s3 sync ./local-folder s3://my-bucket-name/folder/

# Sync bucket -> local folder
aws s3 sync s3://my-bucket-name/folder/ ./local-folder

# Sync bucket -> bucket
aws s3 sync s3://source-bucket s3://dest-bucket

# Sync and delete files at destination not present at source
aws s3 sync ./local-folder s3://my-bucket-name/ --delete

# Dry run (preview changes only)
aws s3 sync ./local-folder s3://my-bucket-name/ --dryrun

# Exclude/include patterns
aws s3 sync ./local-folder s3://my-bucket-name/ --exclude "*.log" --include "*.csv"
```

### 2.6 Moving & removing
```bash
# Move (copy + delete source) a file
aws s3 mv s3://my-bucket-name/file.txt s3://my-bucket-name/archive/file.txt

# Move locally <-> S3
aws s3 mv ./file.txt s3://my-bucket-name/

# Delete a single object
aws s3 rm s3://my-bucket-name/file.txt

# Delete all objects under a prefix (recursive)
aws s3 rm s3://my-bucket-name/folder/ --recursive

# Delete with exclude/include filters
aws s3 rm s3://my-bucket-name/ --recursive --exclude "*" --include "*.tmp"
```

### 2.7 Presigned URLs
```bash
# Generate a temporary URL (default 1 hour expiry)
aws s3 presign s3://my-bucket-name/file.txt

# Custom expiry (seconds)
aws s3 presign s3://my-bucket-name/file.txt --expires-in 3600
```

### 2.8 Website hosting (basic, via s3 CLI)
```bash
aws s3 website s3://my-bucket-name/ --index-document index.html --error-document error.html
```

---

## 3. AWS CLI — S3API Commands (`aws s3api`)

Low-level commands mapping directly to the S3 REST API — used for configuration, metadata, and advanced features not available in `aws s3`.

### 3.1 Bucket details & policies
```bash
# Get bucket location/region
aws s3api get-bucket-location --bucket my-bucket-name

# Get bucket policy
aws s3api get-bucket-policy --bucket my-bucket-name

# Set/attach a bucket policy from a JSON file
aws s3api put-bucket-policy --bucket my-bucket-name --policy file://policy.json

# Delete bucket policy
aws s3api delete-bucket-policy --bucket my-bucket-name

# Get bucket ACL
aws s3api get-bucket-acl --bucket my-bucket-name

# Put bucket ACL (e.g., private/public-read)
aws s3api put-bucket-acl --bucket my-bucket-name --acl private
```

### 3.2 Versioning
```bash
# Enable versioning
aws s3api put-bucket-versioning --bucket my-bucket-name --versioning-configuration Status=Enabled

# Suspend versioning
aws s3api put-bucket-versioning --bucket my-bucket-name --versioning-configuration Status=Suspended

# Check versioning status
aws s3api get-bucket-versioning --bucket my-bucket-name

# List all object versions
aws s3api list-object-versions --bucket my-bucket-name

# Delete a specific version of an object
aws s3api delete-object --bucket my-bucket-name --key file.txt --version-id "versionIdHere"
```

### 3.3 Encryption
```bash
# Set default bucket encryption (SSE-S3)
aws s3api put-bucket-encryption --bucket my-bucket-name \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# Get bucket encryption config
aws s3api get-bucket-encryption --bucket my-bucket-name
```

### 3.4 Lifecycle rules
```bash
# Apply a lifecycle configuration from JSON file
aws s3api put-bucket-lifecycle-configuration --bucket my-bucket-name --lifecycle-configuration file://lifecycle.json

# Get current lifecycle rules
aws s3api get-bucket-lifecycle-configuration --bucket my-bucket-name

# Delete lifecycle configuration
aws s3api delete-bucket-lifecycle --bucket my-bucket-name
```

Example `lifecycle.json`:
```json
{
  "Rules": [
    {
      "ID": "MoveToGlacierAfter30Days",
      "Filter": {"Prefix": ""},
      "Status": "Enabled",
      "Transitions": [
        {"Days": 30, "StorageClass": "GLACIER"}
      ],
      "Expiration": {"Days": 365}
    }
  ]
}
```

### 3.5 CORS
```bash
aws s3api put-bucket-cors --bucket my-bucket-name --cors-configuration file://cors.json
aws s3api get-bucket-cors --bucket my-bucket-name
aws s3api delete-bucket-cors --bucket my-bucket-name
```

### 3.6 Tagging
```bash
aws s3api put-bucket-tagging --bucket my-bucket-name --tagging 'TagSet=[{Key=Env,Value=Prod}]'
aws s3api get-bucket-tagging --bucket my-bucket-name
aws s3api delete-bucket-tagging --bucket my-bucket-name
```

### 3.7 Object metadata & operations
```bash
# Get object metadata (without downloading)
aws s3api head-object --bucket my-bucket-name --key file.txt

# Copy an object (server-side, no download)
aws s3api copy-object --bucket dest-bucket --key file.txt \
  --copy-source source-bucket/file.txt

# Restore an object from Glacier
aws s3api restore-object --bucket my-bucket-name --key file.txt \
  --restore-request '{"Days":5,"GlacierJobParameters":{"Tier":"Standard"}}'
```

### 3.8 Multipart upload (manual, low-level)
```bash
# 1. Initiate
aws s3api create-multipart-upload --bucket my-bucket-name --key bigfile.zip

# 2. Upload parts (repeat per part with returned UploadId)
aws s3api upload-part --bucket my-bucket-name --key bigfile.zip \
  --part-number 1 --body part1.zip --upload-id "UPLOAD_ID"

# 3. Complete
aws s3api complete-multipart-upload --bucket my-bucket-name --key bigfile.zip \
  --upload-id "UPLOAD_ID" --multipart-upload file://parts.json

# Abort a multipart upload
aws s3api abort-multipart-upload --bucket my-bucket-name --key bigfile.zip --upload-id "UPLOAD_ID"

# List in-progress multipart uploads
aws s3api list-multipart-uploads --bucket my-bucket-name
```

### 3.9 Public access block
```bash
aws s3api put-public-access-block --bucket my-bucket-name \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws s3api get-public-access-block --bucket my-bucket-name
```

---

## 4. Python (boto3) — Setup

```python
import boto3
from botocore.exceptions import ClientError

# Client (low-level, closer to REST API)
s3_client = boto3.client(
    "s3",
    aws_access_key_id="YOUR_KEY",       # optional if configured via aws configure
    aws_secret_access_key="YOUR_SECRET",
    region_name="ap-south-1"
)

# Resource (high-level, more Pythonic)
s3_resource = boto3.resource("s3")
```

> Tip: In production, avoid hardcoding keys — let boto3 pick up credentials from `~/.aws/credentials`, environment variables, or an IAM role.

---

## 5. Python (boto3) — Bucket Operations

```python
# List all buckets
response = s3_client.list_buckets()
for bucket in response["Buckets"]:
    print(bucket["Name"])

# Create a bucket
s3_client.create_bucket(
    Bucket="my-bucket-name",
    CreateBucketConfiguration={"LocationConstraint": "ap-south-1"}
)

# Delete a bucket (must be empty)
s3_client.delete_bucket(Bucket="my-bucket-name")

# Check if a bucket exists / you have access
try:
    s3_client.head_bucket(Bucket="my-bucket-name")
    print("Bucket exists")
except ClientError:
    print("Bucket does not exist or no access")

# Enable versioning
s3_client.put_bucket_versioning(
    Bucket="my-bucket-name",
    VersioningConfiguration={"Status": "Enabled"}
)

# Get bucket region
loc = s3_client.get_bucket_location(Bucket="my-bucket-name")
print(loc["LocationConstraint"])

# Set bucket policy
import json
policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": "*",
        "Action": "s3:GetObject",
        "Resource": "arn:aws:s3:::my-bucket-name/*"
    }]
}
s3_client.put_bucket_policy(Bucket="my-bucket-name", Policy=json.dumps(policy))

# Enable default encryption
s3_client.put_bucket_encryption(
    Bucket="my-bucket-name",
    ServerSideEncryptionConfiguration={
        "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
    }
)

# Set lifecycle rule
s3_client.put_bucket_lifecycle_configuration(
    Bucket="my-bucket-name",
    LifecycleConfiguration={
        "Rules": [{
            "ID": "ExpireOldFiles",
            "Filter": {"Prefix": ""},
            "Status": "Enabled",
            "Expiration": {"Days": 365}
        }]
    }
)

# Add bucket tags
s3_client.put_bucket_tagging(
    Bucket="my-bucket-name",
    Tagging={"TagSet": [{"Key": "Env", "Value": "Prod"}]}
)

# Block public access
s3_client.put_public_access_block(
    Bucket="my-bucket-name",
    PublicAccessBlockConfiguration={
        "BlockPublicAcls": True,
        "IgnorePublicAcls": True,
        "BlockPublicPolicy": True,
        "RestrictPublicBuckets": True
    }
)
```

---

## 6. Python (boto3) — Object Operations

### 6.1 Upload
```python
# Upload a file
s3_client.upload_file(
    Filename="localfile.txt",     # local path
    Bucket="my-bucket-name",
    Key="folder/localfile.txt"    # S3 object key
)

# Upload with extra args (storage class, encryption, content type)
s3_client.upload_file(
    Filename="localfile.txt",
    Bucket="my-bucket-name",
    Key="folder/localfile.txt",
    ExtraArgs={
        "StorageClass": "STANDARD_IA",
        "ServerSideEncryption": "AES256",
        "ContentType": "text/plain"
    }
)

# Upload from an in-memory object (bytes/BytesIO)
import io
data = io.BytesIO(b"Hello, S3!")
s3_client.upload_fileobj(data, "my-bucket-name", "hello.txt")

# Upload using put_object (good for small text/string content)
s3_client.put_object(
    Bucket="my-bucket-name",
    Key="notes.txt",
    Body="Some text content",
    ContentType="text/plain"
)
```

### 6.2 Download
```python
# Download to local file
s3_client.download_file(
    Bucket="my-bucket-name",
    Key="folder/localfile.txt",
    Filename="downloaded.txt"
)

# Download into memory
buffer = io.BytesIO()
s3_client.download_fileobj("my-bucket-name", "folder/localfile.txt", buffer)
buffer.seek(0)
content = buffer.read()

# Get object directly (streaming body)
response = s3_client.get_object(Bucket="my-bucket-name", Key="folder/localfile.txt")
content = response["Body"].read().decode("utf-8")
```

### 6.3 List objects
```python
# List objects with a prefix
response = s3_client.list_objects_v2(Bucket="my-bucket-name", Prefix="folder/")
for obj in response.get("Contents", []):
    print(obj["Key"], obj["Size"], obj["LastModified"])

# Paginate through large buckets
paginator = s3_client.get_paginator("list_objects_v2")
for page in paginator.paginate(Bucket="my-bucket-name"):
    for obj in page.get("Contents", []):
        print(obj["Key"])
```

### 6.4 Delete
```python
# Delete a single object
s3_client.delete_object(Bucket="my-bucket-name", Key="folder/localfile.txt")

# Delete multiple objects in one call
s3_client.delete_objects(
    Bucket="my-bucket-name",
    Delete={"Objects": [{"Key": "file1.txt"}, {"Key": "file2.txt"}]}
)

# Delete all objects under a prefix
objects_to_delete = s3_client.list_objects_v2(Bucket="my-bucket-name", Prefix="folder/")
if "Contents" in objects_to_delete:
    keys = [{"Key": obj["Key"]} for obj in objects_to_delete["Contents"]]
    s3_client.delete_objects(Bucket="my-bucket-name", Delete={"Objects": keys})
```

### 6.5 Copy objects
```python
# Copy within/between buckets (server-side, no download)
s3_client.copy_object(
    Bucket="dest-bucket",
    Key="file.txt",
    CopySource={"Bucket": "source-bucket", "Key": "file.txt"}
)

# High-level copy (auto-handles multipart for large files)
s3_client.copy(
    CopySource={"Bucket": "source-bucket", "Key": "file.txt"},
    Bucket="dest-bucket",
    Key="file.txt"
)
```

### 6.6 Presigned URLs
```python
# Generate a presigned GET URL (share/download link)
url = s3_client.generate_presigned_url(
    "get_object",
    Params={"Bucket": "my-bucket-name", "Key": "file.txt"},
    ExpiresIn=3600  # seconds
)
print(url)

# Generate a presigned PUT URL (let others upload without credentials)
upload_url = s3_client.generate_presigned_url(
    "put_object",
    Params={"Bucket": "my-bucket-name", "Key": "upload-here.txt"},
    ExpiresIn=3600
)

# Presigned POST (form-based upload with conditions)
presigned_post = s3_client.generate_presigned_post(
    Bucket="my-bucket-name",
    Key="uploads/${filename}",
    ExpiresIn=3600
)
```

### 6.7 Object metadata & existence checks
```python
# Check if an object exists / get metadata without downloading
try:
    head = s3_client.head_object(Bucket="my-bucket-name", Key="file.txt")
    print(head["ContentLength"], head["LastModified"])
except ClientError as e:
    if e.response["Error"]["Code"] == "404":
        print("Object not found")

# Set/get object tags
s3_client.put_object_tagging(
    Bucket="my-bucket-name",
    Key="file.txt",
    Tagging={"TagSet": [{"Key": "Type", "Value": "Report"}]}
)
tags = s3_client.get_object_tagging(Bucket="my-bucket-name", Key="file.txt")
```

### 6.8 Multipart upload (Python, automatic via TransferConfig)
```python
from boto3.s3.transfer import TransferConfig

config = TransferConfig(
    multipart_threshold=1024 * 1024 * 25,  # 25 MB threshold
    multipart_chunksize=1024 * 1024 * 25,
    max_concurrency=10,
    use_threads=True
)

s3_client.upload_file(
    "bigfile.zip", "my-bucket-name", "bigfile.zip",
    Config=config
)
```

### 6.9 Manual multipart upload (fine-grained control)
```python
key = "bigfile.zip"
mpu = s3_client.create_multipart_upload(Bucket="my-bucket-name", Key=key)
upload_id = mpu["UploadId"]

parts = []
part_number = 1
with open("bigfile.zip", "rb") as f:
    while chunk := f.read(1024 * 1024 * 10):  # 10 MB chunks
        part = s3_client.upload_part(
            Bucket="my-bucket-name", Key=key,
            PartNumber=part_number, UploadId=upload_id, Body=chunk
        )
        parts.append({"PartNumber": part_number, "ETag": part["ETag"]})
        part_number += 1

s3_client.complete_multipart_upload(
    Bucket="my-bucket-name", Key=key, UploadId=upload_id,
    MultipartUpload={"Parts": parts}
)
```

### 6.10 Sync a local folder to S3 (Python equivalent of `aws s3 sync`)
```python
import os

def sync_folder_to_s3(local_folder, bucket, prefix=""):
    for root, _, files in os.walk(local_folder):
        for filename in files:
            local_path = os.path.join(root, filename)
            relative_path = os.path.relpath(local_path, local_folder)
            s3_key = os.path.join(prefix, relative_path).replace("\\", "/")
            s3_client.upload_file(local_path, bucket, s3_key)
            print(f"Uploaded: {s3_key}")

sync_folder_to_s3("./local-folder", "my-bucket-name", prefix="folder")
```

### 6.11 Using the resource interface (alternative style)
```python
bucket = s3_resource.Bucket("my-bucket-name")

# Upload
bucket.upload_file("localfile.txt", "folder/localfile.txt")

# List objects
for obj in bucket.objects.filter(Prefix="folder/"):
    print(obj.key, obj.size)

# Download
bucket.download_file("folder/localfile.txt", "downloaded.txt")

# Delete
obj = s3_resource.Object("my-bucket-name", "folder/localfile.txt")
obj.delete()
```

---

## 7. Error Handling (Python)

```python
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError

try:
    s3_client.upload_file("localfile.txt", "my-bucket-name", "file.txt")
except FileNotFoundError:
    print("Local file not found")
except NoCredentialsError:
    print("AWS credentials not found")
except ClientError as e:
    error_code = e.response["Error"]["Code"]
    print(f"AWS error: {error_code} - {e.response['Error']['Message']}")
except EndpointConnectionError:
    print("Could not connect to AWS endpoint")
```

---

## 8. Quick Reference — CLI vs Python Equivalents

| Task | CLI Command | Python (boto3) |
|---|---|---|
| List buckets | `aws s3 ls` | `s3_client.list_buckets()` |
| Create bucket | `aws s3 mb s3://bucket` | `s3_client.create_bucket(Bucket=...)` |
| Delete bucket | `aws s3 rb s3://bucket --force` | `s3_client.delete_bucket(Bucket=...)` |
| Upload file | `aws s3 cp file s3://bucket/` | `s3_client.upload_file(...)` |
| Download file | `aws s3 cp s3://bucket/file .` | `s3_client.download_file(...)` |
| List objects | `aws s3 ls s3://bucket --recursive` | `s3_client.list_objects_v2(...)` |
| Delete object | `aws s3 rm s3://bucket/file` | `s3_client.delete_object(...)` |
| Sync folder | `aws s3 sync ./dir s3://bucket/` | custom loop with `upload_file` |
| Copy object | n/a (use `aws s3 cp` for S3-to-S3) | `s3_client.copy_object(...)` |
| Presigned URL | `aws s3 presign s3://bucket/file` | `s3_client.generate_presigned_url(...)` |
| Versioning | `aws s3api put-bucket-versioning` | `s3_client.put_bucket_versioning(...)` |
| Bucket policy | `aws s3api put-bucket-policy` | `s3_client.put_bucket_policy(...)` |
| Lifecycle rules | `aws s3api put-bucket-lifecycle-configuration` | `s3_client.put_bucket_lifecycle_configuration(...)` |

---

## 9. Best Practices

- Never hardcode AWS keys in scripts — use IAM roles, environment variables, or `~/.aws/credentials`.
- Enable **versioning** and **default encryption** on production buckets.
- Use **bucket policies + public access block** to avoid accidental public exposure.
- Use `aws s3 sync` (not repeated `cp`) for directory-level uploads — it only transfers changed files.
- For files >100 MB, rely on multipart upload (`TransferConfig` in boto3, automatic in CLI).
- Use **lifecycle rules** to auto-transition old data to cheaper storage classes (IA, Glacier) and expire it.
- Use presigned URLs instead of making objects public when sharing temporarily.
- Always paginate (`list_objects_v2` + paginator) when listing buckets with many objects — a single call caps at 1000 keys.
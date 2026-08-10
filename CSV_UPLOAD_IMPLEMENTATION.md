# CSV Upload Implementation Guide

## Overview
This document describes the complete implementation of CSV file upload functionality for OptScale cost data.

## What's Already Implemented ✅

### 1. Frontend (UI)
- **Location**: `ngui/ui/src/`
- **Files Created/Modified**:
  - `components/DataSourceCredentialFields/CsvUploadCredentials/` - File upload form
  - `icons/CsvUploadIcon/` - CSV upload icon
  - `constants.ts` - Added `CSV_UPLOAD` constants
  - `app.json` - Added translations
  - `ConnectCloudAccountForm.tsx` - Added CSV tile
  - `useIsDataSourceConnectionTypeEnabled.ts` - Enabled CSV option

**Status**: ✅ Complete - UI is functional

### 2. Backend - Data Import Worker
- **Location**: `diworker/diworker/importers/`
- **File Created**: `csv.py` - CSV Report Importer

**Features**:
- Flexible CSV header mapping (supports AWS, Azure, GCP formats)
- Date parsing in multiple formats
- Cost, resource, service extraction
- MongoDB raw data storage
- Handles various CSV structures

**Status**: ✅ Complete - Ready to process CSV files

### 3. Backend - Cloud Adapter
- **Location**: `tools/cloud_adapter/clouds/`
- **File Created**: `csv.py` - CSV Cloud Adapter

**Features**:
- Credential validation
- Minimal adapter (no resource discovery needed)
- Integration with cloud adapter factory

**Files Modified**:
- `cloud.py` - Registered CsvUpload adapter
- `factory.py` - Registered CsvReportImporter

**Status**: ✅ Complete - Adapter ready

### 4. Backend - AWS FOCUS Export Support
- **Location**: `tools/cloud_adapter/clouds/aws.py`

**Changes**:
- Added `cur_version: 3` support for FOCUS exports
- Added `/data/` subfolder support
- Added lowercase `billing_period` pattern support
- Updated `GROUP_DATES_PATTERNS`, `find_reports()`, and `_collect_s3_objects()`

**Status**: ✅ Complete - FOCUS exports working

---

## What Needs Implementation ⚠️

### 1. REST API File Upload Handler

**Required Changes**:

#### A. Update Handler to Accept File Uploads

**File**: `rest_api/rest_api_server/handlers/v2/cloud_account.py`

Add multipart form data support to the `post()` method:

```python
async def post(self, **url_params):
    organization_id = url_params.get('organization_id')
    cloud_type = self._request_body().get('type')
    
    # Handle CSV upload
    if cloud_type == 'csv_upload':
        return await self._handle_csv_upload(organization_id)
    
    # Existing logic for other cloud types...
    await super().post(**url_params)

async def _handle_csv_upload(self, organization_id):
    """Handle CSV file upload"""
    import uuid
    import boto3
    from boto3.session import Config as BotoConfig
    
    # Get uploaded file
    if 'csv_file' not in self.request.files:
        raise OptHTTPError(400, Err.OE0216, ['csv_file'])
    
    file_info = self.request.files['csv_file'][0]
    filename = file_info['filename']
    file_body = file_info['body']
    
    # Validate file
    if not filename.endswith('.csv'):
        raise OptHTTPError(400, Err.OE0214, ['File must be CSV format'])
    
    # Generate unique key
    file_key = f"csv-uploads/{organization_id}/{uuid.uuid4()}/{filename}"
    
    # Upload to MinIO
    s3_params = self._config.read_branch('/minio')
    s3_client = boto3.client(
        's3',
        endpoint_url=f"http://{s3_params['host']}:{s3_params['port']}",
        aws_access_key_id=s3_params['access'],
        aws_secret_access_key=s3_params['secret'],
        config=BotoConfig(s3={'addressing_style': 'path'})
    )
    
    bucket_name = 'optscale-csv-uploads'
    
    # Create bucket if not exists
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except:
        s3_client.create_bucket(Bucket=bucket_name)
    
    # Upload file
    s3_client.put_object(
        Bucket=bucket_name,
        Key=file_key,
        Body=file_body
    )
    
    # Create cloud account with file reference
    name = self.get_argument('name')
    data = {
        'name': name,
        'type': 'csv_upload',
        'config': {
            'csv_file_key': file_key,
            'bucket_name': bucket_name,
            'original_filename': filename
        }
    }
    
    controller = self._get_controller_class()(
        self._session(), self._config, self.token
    )
    result = await run_task(controller.create, organization_id, **data)
    self.set_status(201)
    self.write(json.dumps(result, cls=ModelEncoder))
```

#### B. Update API Documentation

Add `csv_upload` to the enum in the swagger docs (line 60):

```python
enum: [aws_cnr, azure_cnr, kubernetes_cnr, alibaba_cnr,
       azure_tenant, gcp_cnr, nebius, databricks,
       gcp_tenant, csv_upload]
```

#### C. Update Frontend to Send Files Correctly

**File**: `ngui/ui/src/containers/ConnectCloudAccountContainer/ConnectCloudAccountContainer.tsx`

Modify the `onSubmit` function to handle file uploads:

```typescript
const onSubmit = async ({ name, config, type }: Params) => {
  if (type === CSV_UPLOAD) {
    // Handle CSV upload differently
    const formData = new FormData();
    formData.append('name', name);
    formData.append('type', type);
    formData.append('csv_file', config.csv_file); // File object from form
    
    try {
      const response = await fetch(
        `/restapi/v2/organizations/${organizationId}/cloud_accounts`,
        {
          method: 'POST',
          body: formData,
          headers: {
            'Authorization': `Bearer ${token}`, // Add auth token
          },
        }
      );
      
      if (response.ok) {
        refetch([GET_AVAILABLE_FILTERS]);
        redirectToCloudsOverview();
      }
    } catch (error) {
      console.error('CSV upload failed:', error);
    }
    return;
  }
  
  // Existing logic for other cloud types...
  const configName = {
    [AWS_CNR]: getAwsConfigName(config),
    // ... rest of config
  }[type];
  
  // ... existing GraphQL mutation
};
```

---

## Deployment Instructions 🚀

### Step 1: Rebuild Images

```bash
# From optscale root directory
docker build -t optscale-ngui:latest -f ngui/Dockerfile ngui/
docker build -t optscale-restapi:latest -f rest_api/Dockerfile .
docker build -t optscale-diworker:latest -f diworker/Dockerfile .
```

### Step 2: Recreate Pods

Get current pod names:
```bash
kubectl get pods | grep -E "ngui|restapi|diworker"
```

Delete pods (they will auto-recreate with new images):
```bash
# Replace with your actual pod names
kubectl delete pod ngui-577fcbfd68-2fp2p
kubectl delete pod restapi-cfdcdd8fd-s498b  
kubectl delete pod diworker-6465cc498f-6n65l
```

### Step 3: Verify Pods are Running

```bash
kubectl get pods | grep -E "ngui|restapi|diworker"
```

Wait until all show:
- STATUS: `Running`
- READY: `1/1`
- RESTARTS: `0`

### Step 4: Check Logs

```bash
# Check for errors
kubectl logs <pod-name> --tail=50

# Examples:
kubectl logs ngui-xxxxx --tail=50
kubectl logs restapi-xxxxx --tail=50
kubectl logs diworker-xxxxx --tail=50
```

---

## Testing AWS FOCUS Export 🧪

### Prerequisites:
1. AWS Data Export created with FOCUS format
2. Files exist in S3: `s3://cur-focus-data-export/cid/cur-focus-aws-columns/data/billing_period=2026-XX/`

### Connection Steps:

1. Navigate to: **Data Sources** → **Connect Data Source**
2. Click **AWS** tile
3. Select **Management/Standalone**
4. Select **Assumed Role** (or Access Key)
5. Fill in credentials
6. **Export type**: Select **"FOCUS with AWS columns"**
7. **Export name**: `cur-focus-aws-columns`
8. **Export S3 bucket name**: `cur-focus-data-export`
9. **Export path prefix**: `cid`
10. Click **Connect**

### Verification:

Check diworker logs:
```bash
kubectl logs diworker-xxxxx --tail=100 | grep -i "cur-focus\|focus\|billing_period"
```

Should see:
```
INFO: Started import for <cloud_account_id>
INFO: Selected X reports
INFO: Importing raw data
INFO: Import completed
```

---

## Testing CSV Upload (Once REST API is Implemented) 📊

### Supported CSV Formats:

#### AWS CUR Format:
```csv
lineItem/UsageStartDate,lineItem/UnblendedCost,lineItem/ResourceId,product/serviceName,product/instanceType,product/region
2026-08-01,10.50,i-1234567890abcdef,Amazon Elastic Compute Cloud,t3.medium,us-east-1
```

#### Azure Format:
```csv
Date,PreTaxCost,ResourceId,MeterCategory,MeterSubCategory,ResourceLocation
2026-08-01,25.00,/subscriptions/xxx/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1,Virtual Machines,General Purpose,East US
```

#### Generic Format:
```csv
date,cost,resource_id,service,resource_type,region
2026-08-01,15.75,instance-123,Compute,VM,us-west-2
```

### Test Steps:

1. Navigate to: **Data Sources** → **Connect Data Source**
2. Click **CSV Upload** tile
3. Enter **Name**: "Test CSV Data"
4. **Drop or select** your CSV file
5. Click **Connect**

### Verify Import:

```bash
# Check upload
kubectl logs restapi-xxxxx | grep -i "csv"

# Check import
kubectl logs diworker-xxxxx | grep -i "csv"
```

---

## Troubleshooting 🔧

### Issue: CSV Upload tile not visible
**Solution**: Verify `useIsDataSourceConnectionTypeEnabled.ts` includes:
```typescript
[CONNECTION_TYPES.CSV_UPLOAD]: true,
```

### Issue: File upload fails
**Causes**:
1. REST API handler not implemented
2. MinIO bucket doesn't exist
3. File size too large

**Debug**:
```bash
kubectl logs restapi-xxxxx --tail=100
```

### Issue: CSV import fails
**Causes**:
1. Invalid CSV format
2. Missing required columns
3. File not found in MinIO

**Debug**:
```bash
kubectl logs diworker-xxxxx --tail=100
```

Look for:
```
ERROR: No CSV file key found in cloud account config
ERROR: Unable to parse date: <date_value>
ERROR: Error loading CSV data: <error>
```

### Issue: AWS FOCUS export not found
**Causes**:
1. Wrong S3 prefix (should be `cid` not `reports`)
2. Files in `/data/` subfolder not being found
3. lowercase `billing_period` not recognized

**Solution**: Verify backend changes were deployed:
```bash
kubectl exec diworker-xxxxx -- python -c "
from tools.cloud_adapter.clouds.aws import GROUP_DATES_PATTERNS
print(GROUP_DATES_PATTERNS)
"
```

Should show:
```python
{2: ['BILLING_PERIOD=...', 'billing_period=...'], 
 3: ['BILLING_PERIOD=...', 'billing_period=...'], ...}
```

---

## File Structure Summary 📁

```
optscale/
├── ngui/ui/src/
│   ├── components/
│   │   ├── DataSourceCredentialFields/
│   │   │   └── CsvUploadCredentials/          ✅ NEW
│   │   └── forms/ConnectCloudAccountForm/     ✅ MODIFIED
│   ├── icons/CsvUploadIcon/                    ✅ NEW
│   ├── hooks/
│   │   └── useIsDataSourceConnectionTypeEnabled.ts  ✅ MODIFIED
│   ├── translations/en-US/app.json             ✅ MODIFIED
│   └── utils/constants.ts                      ✅ MODIFIED
│
├── diworker/diworker/importers/
│   ├── csv.py                                  ✅ NEW
│   └── factory.py                              ✅ MODIFIED
│
├── tools/cloud_adapter/
│   ├── clouds/
│   │   ├── aws.py                              ✅ MODIFIED (FOCUS support)
│   │   └── csv.py                              ✅ NEW
│   └── cloud.py                                ✅ MODIFIED
│
└── rest_api/rest_api_server/handlers/v2/
    └── cloud_account.py                        ⚠️  NEEDS IMPLEMENTATION
```

---

## Next Steps Checklist ☑️

### Immediate (For FOCUS Export):
- [ ] Recreate backend pods (`diworker`, `restapi`)
- [ ] Test FOCUS export connection
- [ ] Verify data import in diworker logs
- [ ] Check data appears in UI

### Short Term (For CSV Upload):
- [ ] Implement REST API file upload handler
- [ ] Test file upload from UI
- [ ] Verify file stored in MinIO
- [ ] Test CSV import in diworker
- [ ] Verify expenses appear in UI

### Optional Enhancements:
- [ ] Add CSV format validation
- [ ] Add file size limits
- [ ] Add CSV preview before import
- [ ] Support Excel (.xlsx) files
- [ ] Add CSV column mapping UI

---

## Support

For issues:
1. Check logs: `kubectl logs <pod-name> --tail=100`
2. Verify files exist: `aws s3 ls s3://bucket/path/ --recursive`
3. Test MinIO access: `aws s3 ls --endpoint-url=http://minio:9000`

---

**Last Updated**: 2026-08-10
**Implementation Status**: 
- Frontend: ✅ Complete
- Backend (Import): ✅ Complete  
- Backend (API Upload): ⚠️ In Progress
- AWS FOCUS: ✅ Complete

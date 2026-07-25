# Bright Data MCP Configuration for Sangam

## Prerequisites

1. **Bright Data Account** - Sign up at https://brightdata.com
2. **API Token** - Generate from Bright Data dashboard
3. **Datasets** - Enable the required datasets in your account

## Quick Setup

### 1. Install Bright Data MCP Package

```bash
npm install -g @brightdata/mcp
```

### 2. Configure OpenCode

Create/update `opencode.json` in your project root:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "brightData": {
      "type": "local",
      "enabled": true,
      "command": [
        "npx",
        "-y",
        "@brightdata/mcp"
      ],
      "environment": {
        "API_TOKEN": "YOUR_BRIGHT_DATA_API_TOKEN_HERE",
        "PRO_MODE": "true"
      }
    }
  }
}
```

Replace `YOUR_BRIGHT_DATA_API_TOKEN_HERE` with your actual token.

### 3. Enable Required Datasets

In Bright Data dashboard, enable these datasets for government data scraping:

| Dataset | Purpose | GovStack Capability |
|---------|---------|---------------------|
| `gstn_dataset` | GSTIN validation, return filing | `gstn.validate-gstin`, `gstn.get-returns` |
| `mca_dataset` | Company CIN lookup | `mca.get-company` |
| `udyam_dataset` | MSME Udyam validation | `udyam.validate` |
| `schemes_dataset` | Government scheme discovery | `schemes.discover` |
| `mospi_dataset` | Economic indicators, labor data | `mospi.get-indicator`, `mospi.get-labor-data` |
| `gatishakti_dataset` | PM GatiShakti geospatial | `gatishakti.analyze-location` |
| `power_dataset` | National Power Portal | `power.get-data` |

### 4. Set Environment Variable

```bash
export BRIGHTDATA_API_TOKEN="your_token_here"
```

Or add to your `.env` file:
```
BRIGHTDATA_API_TOKEN=your_token_here
```

## Usage in Sangam

Once configured, the GovStack capabilities will use real Bright Data scraping:

```python
from app.core.govstack import GovStackService
import os

service = GovStackService(brightdata_token=os.getenv("BRIGHTDATA_API_TOKEN"))

# Real GSTN validation
result = await service.validate_gstin("29AAAAA0000A1Z5")

# Real MCA company lookup
result = await service.get_company_details("U74999KA2020PTC123456")

# Real scheme discovery
schemes = await service.discover_schemes({
    "industry": "manufacturing",
    "state": "Karnataka",
    "size": "small"
})
```

## Rate Limits

| Capability | Rate Limit | Notes |
|------------|------------|-------|
| GSTN | 60/min | Per IP, cached 1hr |
| MCA | 60/min | Per IP, cached 1hr |
| Udyam | 60/min | Per IP, cached 1hr |
| Schemes | 30/min | Heavier queries |
| MoSPI | 60/min | Cached 6hr |
| GatiShakti | 30/min | Geospatial queries |
| Power | 60/min | Time-series data |

## Testing Without Token

The GovStack service includes mock fallbacks for development. When `BRIGHTDATA_API_TOKEN` is not set, it returns realistic test data.

## Production Notes

1. **GSTN** - Requires GSP (GST Suvidha Provider) credentials for production API access
2. **MCA** - Public API available, but rate limited
3. **Udyam** - KredX DTX platform API (paid)
4. **MoSPI/NSO** - Free public APIs via unitdata Python library
5. **PM GatiShakti** - Free geospatial API
6. **National Power Portal** - Free power sector API

For production, you may want to integrate direct APIs where available and use Bright Data as a fallback for web scraping.
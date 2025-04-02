# G2B Public Data Portal API Integration Report

## Overview

This document summarizes the results of integrating the G2B (Korea Public Procurement Service) API from the Public Data Portal into our project and its current status.

## Implementation Details

1. **API Client Implementation**: Implemented a client for communicating with the G2B API in `backend/utils/crawl/g2b_api.py`
2. **Key Features**:
   - Bid listing search (Construction, Goods, Services, Foreign)
   - API connection testing
   - Result storage and Excel conversion
   - Error handling and logging

## Current Status

Currently, the following error occurs when calling the API:

```xml
<OpenAPI_ServiceResponse>
    <cmmMsgHeader>
        <errMsg>SERVICE ERROR</errMsg>
        <returnAuthMsg>NO_OPENAPI_SERVICE_ERROR</returnAuthMsg>
        <returnReasonCode>12</returnReasonCode>
    </cmmMsgHeader>
</OpenAPI_ServiceResponse>
```

This error indicates that service approval is required from the Public Data Portal.

## Required Actions

To use the API normally, the following steps are necessary:

1. **Create a Public Data Portal Account**: Create an account at [Public Data Portal](https://www.data.go.kr) if you don't have one
2. **Apply for API Service**:
   - Visit the [G2B Bid Announcement Information Service](https://www.data.go.kr/data/15129394/openapi.do) page
   - Click the "Apply for Use" button
   - Fill out the application form (purpose of use, period of use, etc.)
3. **Wait for Approval**: It may take up to 2-3 days for approval after application
4. **Update API Key**: Update the API key in the `.env` file after approval

## Environment Configuration

The API client uses the following environment variables:

- `G2B_API_KEY_ENCODING`: URL-encoded API key
- `G2B_API_KEY_DECODING`: Decoded API key (optional)

## Technical Issues and Solutions

1. **SSL Certificate Error**: SSL certificate issues with APIs.data.go.kr cause `SSLV3_ALERT_ILLEGAL_PARAMETER` errors when making HTTPS requests
   - **Solution**: Changed to use HTTP protocol

2. **URL Encoding Issues**: Double encoding occurred when passing the API key in the `serviceKey` parameter
   - **Solution**: Direct URL construction and control of encoding parameters

3. **XML Response Handling**: Responses are provided in XML format rather than JSON
   - **Solution**: Added XML parser to process error messages and response data

## API Endpoints

The G2B API provides the following endpoints:

1. **Bid Announcement List Queries**:
   - Construction: `/getBidPblancListInfoCnstwk` 
   - Goods: `/getBidPblancListInfoThng`
   - Services: `/getBidPblancListInfoServc`
   - Foreign: `/getBidPblancListInfoFrgcpt`

2. **Bid Announcement Detail Queries**:
   - Construction: `/getBidPblancDetailInfoCnstwk`
   - Goods: `/getBidPblancDetailInfoThng`
   - Services: `/getBidPblancDetailInfoServc`

## Use Cases

After API approval, it can be used in the following ways:

1. **Replace Web Crawling**: Replace existing Selenium-based web crawling with API calls to collect bid information
2. **Hybrid Approach**: Use API for basic information collection and web crawling for complex tasks like file downloads
3. **Performance Improvement**: API calls are faster and more stable than web crawling, improving overall performance

## Conclusion

Currently, approval from the Public Data Portal for the API service is required. After API approval, transitioning from the existing Selenium-based crawling to an API call approach can improve system stability and performance. 
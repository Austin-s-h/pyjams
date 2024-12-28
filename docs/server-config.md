# Server Configuration

## SSL/TLS
- Protocol: TLSv1.3
- Cipher: TLS_AES_256_GCM_SHA384
- Certificate Authority: Google Trust Services WE1
- Valid until: February 1, 2025
- Subject: CN=sansterbioanalytics.com
- SubjectAltName: *.sansterbioanalytics.com

## Server Infrastructure
- CDN: Cloudflare
- HTTP Version: HTTP/2
- Supports H3 (HTTP/3) via alt-svc header
- Load Balancer: Vegur
- Platform: Heroku
- Dyno: web.1
- Response Time: ~1ms average

## Security Headers
```http
X-Content-Type-Options: nosniff
Referrer-Policy: same-origin
Cross-Origin-Opener-Policy: same-origin
X-Frame-Options: DENY
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
Vary: Cookie
Allow: GET
NEL: {"report_to":"heroku-nel","max_age":3600,"success_fraction":0.005,"failure_fraction":0.05,"response_headers":["Via"]}
Report-To: {"group":"heroku-nel","max_age":3600,"endpoints":[{"url":"https://nel.heroku.com/reports?..."}]}
Reporting-Endpoints: heroku-nel=https://nel.heroku.com/reports?...
```

## URL Configuration
- Enforces trailing slashes with 301 redirects
- Content-Type: text/html; charset=utf-8
- Cache Status: Dynamic (cf-cache-status)

## Request Handling
- Forward Protocol: HTTP/2
- Allowed Methods: GET only
- Request ID Generation: UUID v4
- Forward Headers:
  ```http
  fwd: <client-ip>, <cloudflare-ip>
  via: 1.1 vegur
  ```
- Service Metrics:
  - Connect time: 25-32ms
  - Delivery rate: ~98 KB/s
  - Response size: ~835 bytes
  - TCP window: ~213 bytes

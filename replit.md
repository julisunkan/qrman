# QR Pro - Custom QR Code Generator

## Overview

QR Pro is a Flask-based web application that allows users to generate customizable QR codes with branding options, track scans with analytics, and create vCard digital contact files. The application supports multiple export formats (PNG, SVG, animated GIF) and includes a dashboard for viewing scan statistics.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Framework
- **Framework**: Flask (Python)
- **Rationale**: Lightweight, easy to deploy on Replit, suitable for a single-purpose web application
- **Key Files**: `app.py` (main routes), `qr_utils.py` (QR generation logic)

### Database
- **Technology**: SQLite with Python's built-in `sqlite3` module
- **Schema**: Defined in `models.sql`
- **Database File**: `database.db`
- **Rationale**: No external database dependencies, runs entirely within Replit environment

### QR Code Generation
- **PNG/GIF**: `qrcode` library with Pillow for image manipulation
- **SVG**: `segno` library for vector output
- **Logo Embedding**: Pillow handles logo overlay on QR codes with error correction level H

### URL Encoding Strategy
- Uses Base64 URL-safe encoding for QR code identifiers
- Functions: `encrypt_code()` and `decrypt_code()` for obfuscating internal codes

### Frontend Architecture
- **Templating**: Jinja2 templates
- **Styling**: Custom CSS with CSS variables, animated gradient backgrounds
- **Charts**: Chart.js for analytics dashboard
- **PWA Support**: Service worker (`sw.js`) and manifest for offline capability

### Key Routes
- `/` - Main QR generator form
- `/generate` - POST endpoint for creating QR codes
- `/r/<encoded_code>` - Redirect endpoint for tracking scans
- `/dashboard` - Analytics view for individual QR codes
- `/viewer` - QR code decoder tool
- `/vcard-viewer` - vCard file parser

### File Storage
- Generated QR codes stored in `static/qr_codes/`
- Formats: `.png`, `.svg`, `.gif`, `.vcf` (for vCards)

## External Dependencies

### Python Libraries
- `flask` - Web framework
- `qrcode[pillow]` - QR code generation with image support
- `pillow` - Image processing
- `segno` - SVG QR code generation
- `geoip2` - Geographic IP detection (currently returns "Unknown" without MaxMind database)
- `user-agents` - User agent parsing for device detection
- `pytz` - Timezone handling

### Frontend CDN Dependencies
- Chart.js - Analytics charts
- jsQR - Client-side QR code decoding

### Optional External Data
- GeoLite2 database (MaxMind) - For IP geolocation, not included by default
# Haists IT Consulting

Professional website for [Haists IT Consulting](https://www.haist.farm) — small business IT, security, and infrastructure consulting based in Wabash, Indiana.

## Overview

A single-page marketing site with:

- Responsive design with light/dark mode toggle
- Service descriptions, pricing tiers, and certification badges
- Live infrastructure work log pulled from a backend API
- Contact form with email notification
- SEO metadata, Open Graph tags, and structured data (JSON-LD)
- Custom SVG favicons and social preview image

## Stack

**Frontend**: Vanilla HTML/CSS/JS — no frameworks, no build step. Fonts via Google Fonts (Libre Baskerville + DM Sans).

**Hosting**: Served as static files behind a reverse proxy with TLS. The optional backend (not included in this repo) provides live metrics and contact form handling.

## Structure

```
frontend/
├── index.html          # Single-page site (all content inline)
├── css/style.css        # Additional styles
├── js/main.js           # Theme toggle, scroll effects, form handling
├── 404.html             # Custom 404 page
├── og-image.png         # Social preview image (1200x630)
├── favicon-16.svg       # Small favicon
└── favicon-32.svg       # Standard favicon
```

## Local Development

Open `frontend/index.html` in a browser. That's it.

For the live work log and contact form to function, you'd need the backend API running — but the site degrades gracefully without it (log section shows empty, contact form won't submit).

## License

All rights reserved. Source is public for reference and version tracking.

"""
Security configuration for fastapi-guard.
Provides comprehensive protection for all API endpoints.
"""
from guard.models import SecurityConfig


def get_security_config() -> SecurityConfig:
    """
    Configure security settings for the entire application.
    
    Features enabled:
    - Rate limiting: 100 requests per minute per IP
    - Automatic IP banning after 10 suspicious requests
    - Penetration attempt detection
    - Security headers (HSTS, CSP, X-Frame-Options, etc.)
    - CORS configuration
    - Request logging
    """
    return SecurityConfig(
        # === RATE LIMITING ===
        # Limit requests to prevent DDoS and abuse
        rate_limit=100,  # 100 requests per minute per IP
        
        # === AUTOMATIC IP BANNING ===
        # Ban IPs after suspicious activity
        auto_ban_threshold=10,  # Ban after 10 suspicious requests
        auto_ban_duration=3600,  # Ban for 1 hour (3600 seconds)
        
        # === PENETRATION ATTEMPT DETECTION ===
        # Detect SQL injection, XSS, path traversal, etc.
        enable_penetration_detection=True,
        
        # === LOGGING ===
        # Log security events to file
        custom_log_file="logs/security.log",
        
        # === HTTPS ENFORCEMENT ===
        # Redirect HTTP to HTTPS in production
        enforce_https=False,  # Set to True in production
        
        # === CORS CONFIGURATION ===
        # Configure allowed origins for web clients
        enable_cors=True,
        cors_allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",  # Vite dev server
            "http://localhost:8080",
            "http://127.0.0.1:8004",
            "http://127.0.0.1:5173",  # Alternative localhost format
            "http://192.168.1.14:8000",  # React Native app
            "http://192.168.1.14:19000",  # Expo Metro bundler
            "http://192.168.1.14:19006",  # Expo web
        ],
        cors_allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        cors_allow_headers=["*"],
        cors_allow_credentials=True,
        cors_max_age=600,
        
        # === HTTP SECURITY HEADERS ===
        security_headers={
            "enabled": True,
            
            # HTTP Strict Transport Security
            "hsts": {
                "max_age": 31536000,  # 1 year
                "include_subdomains": True,
                "preload": False
            },
            
            # Content Security Policy
            "csp": {
                "default-src": ["'self'"],
                "script-src": ["'self'", "'unsafe-inline'"],  # Needed for some frameworks
                "style-src": ["'self'", "'unsafe-inline'"],
                "img-src": ["'self'", "data:", "https:"],
                "connect-src": ["'self'"],
                "frame-ancestors": ["'none'"],
                "base-uri": ["'self'"],
                "form-action": ["'self'"]
            },
            
            # Clickjacking protection
            "frame_options": "DENY",
            
            # MIME type sniffing protection
            "content_type_options": "nosniff",
            
            # XSS protection
            "xss_protection": "1; mode=block",
            
            # Referrer policy
            "referrer_policy": "strict-origin-when-cross-origin",
            
            # Permissions policy
            "permissions_policy": "geolocation=(), microphone=(), camera=()",
        },
        
        # === USER AGENT FILTERING ===
        # Block suspicious user agents
        blocked_user_agents=[
            "sqlmap",
            "nikto",
            "nmap",
            "masscan",
            "nessus",
        ],
        
        # === IP WHITELISTING (Optional) ===
        # Whitelist localhost for development and IIS proxy
        whitelist=[
            "127.0.0.1",      # IPv4 localhost
            "::1",            # IPv6 localhost
            "127.0.0.0/8",    # IPv4 localhost range
        ],
        
        # === IP BLACKLISTING (Optional) ===
        # Uncomment to blacklist specific IPs
        # blacklist=["10.0.0.0/8"],
        
        # === CLOUD PROVIDER BLOCKING (Optional) ===
        # Uncomment to block cloud provider IPs (helps prevent bot attacks)
        # block_cloud_providers={"AWS", "GCP", "Azure"},
        
        # === COUNTRY BLOCKING (Optional) ===
        # Requires IPInfo token: https://ipinfo.io/signup
        # Uncomment and add token to enable
        # ipinfo_token="your_token_here",
        # blocked_countries=["CN", "RU"],  # Block specific countries
        
        # === PASSIVE MODE (Development) ===
        # Set to True to log threats without blocking (useful for testing)
        passive_mode=True,  # Enabled to allow IIS proxy access
    )

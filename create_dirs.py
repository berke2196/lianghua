#!/usr/bin/env python3

import os
import json

# Create directory structure
dirs = [
    'src/main',
    'src/preload',
    'src/frontend',
    'src/frontend/components',
    'src/frontend/components/pages',
    'src/frontend/components/dashboard',
    'src/frontend/hooks',
    'src/frontend/store',
    'src/frontend/utils',
    'src/frontend/styles',
    'src/frontend/locales',
    'src/frontend/types',
    'src/frontend/services'
]

for d in dirs:
    os.makedirs(d, exist_ok=True)
    print(f"✓ Created: {d}")

print("\nAll directories created successfully!")

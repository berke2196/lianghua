import os
import sys

# Create directory structure
dirs = [
    r'src\backend\models',
    r'src\backend\models\components',
    r'tests\models',
    r'docs\models'
]

for d in dirs:
    os.makedirs(d, exist_ok=True)
    print(f"Created: {d}")

print("Directory structure created successfully")

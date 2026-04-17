#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const dirs = [
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
];

dirs.forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
    console.log(`✓ Created: ${dir}`);
  }
});

console.log('All directories created successfully!');

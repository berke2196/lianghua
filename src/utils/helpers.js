/**
 * Utility functions for the frontend application
 */

/**
 * Format number as currency
 */
export function formatCurrency(value, decimals = 2) {
  return Number(value).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/**
 * Format percentage
 */
export function formatPercent(value, decimals = 2) {
  return `${formatCurrency(value * 100, decimals)}%`;
}

/**
 * Format timestamp
 */
export function formatTime(timestamp) {
  if (!timestamp) return '-';
  const date = new Date(timestamp);
  return date.toLocaleTimeString();
}

/**
 * Format date
 */
export function formatDate(timestamp) {
  if (!timestamp) return '-';
  const date = new Date(timestamp);
  return date.toLocaleDateString();
}

/**
 * Get color based on value (red/green)
 */
export function getPnlColor(value) {
  if (value > 0) return '#00e676';  // Green
  if (value < 0) return '#ff5252';  // Red
  return '#999';                      // Gray
}

/**
 * Get side color
 */
export function getSideColor(side) {
  return side === 'LONG' ? '#00e676' : '#ff5252';
}

/**
 * Parse error message
 */
export function parseError(error) {
  if (typeof error === 'string') return error;
  if (error.message) return error.message;
  if (error.error) return error.error;
  return 'Unknown error occurred';
}

/**
 * Throttle function
 */
export function throttle(func, limit) {
  let inThrottle;
  return function(...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
}

/**
 * Debounce function
 */
export function debounce(func, delay) {
  let timeoutId;
  return function(...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func.apply(this, args), delay);
  };
}

/**
 * Check if value is valid number
 */
export function isValidNumber(value) {
  const num = Number(value);
  return !isNaN(num) && isFinite(num);
}

/**
 * Deep clone object
 */
export function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

/**
 * Merge objects
 */
export function mergeObjects(target, source) {
  return {
    ...target,
    ...source,
  };
}

/**
 * Get contrasting text color
 */
export function getContrastTextColor(bgColor) {
  if (!bgColor) return '#000';
  // Simple contrast calculation
  const rgb = parseInt(bgColor.replace('#', ''), 16);
  const r = (rgb >> 16) & 0xff;
  const g = (rgb >> 8) & 0xff;
  const b = (rgb >> 0) & 0xff;
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  return brightness > 128 ? '#000' : '#fff';
}

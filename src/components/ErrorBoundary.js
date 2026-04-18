import React from 'react';

/**
 * ErrorBoundary Component
 * Catches React rendering errors and displays fallback UI
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('🔴 React Error Caught:', error);
    console.error('Component Stack:', errorInfo.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={styles.container}>
          <div style={styles.content}>
            <h1 style={styles.title}>⚠️ Something Went Wrong</h1>
            <p style={styles.message}>The application encountered an unexpected error.</p>
            <details style={styles.details}>
              <summary>Error Details</summary>
              <pre style={styles.stackTrace}>
                {this.state.error?.toString()}
              </pre>
            </details>
            <button
              onClick={() => window.location.reload()}
              style={styles.button}
            >
              Reload Application
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

const styles = {
  container: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100vh',
    backgroundColor: '#f5f5f5',
    fontFamily: 'Arial, sans-serif',
  },
  content: {
    backgroundColor: 'white',
    padding: '40px',
    borderRadius: '8px',
    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
    maxWidth: '500px',
    textAlign: 'center',
  },
  title: {
    color: '#ff5252',
    fontSize: '24px',
    marginBottom: '10px',
  },
  message: {
    color: '#666',
    fontSize: '16px',
    marginBottom: '20px',
  },
  details: {
    textAlign: 'left',
    backgroundColor: '#f9f9f9',
    padding: '10px',
    borderRadius: '4px',
    marginBottom: '20px',
  },
  stackTrace: {
    backgroundColor: '#f0f0f0',
    padding: '10px',
    borderRadius: '4px',
    overflow: 'auto',
    maxHeight: '200px',
    fontSize: '12px',
  },
  button: {
    backgroundColor: '#40c4ff',
    color: 'white',
    border: 'none',
    padding: '10px 20px',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '14px',
  },
};

export default ErrorBoundary;

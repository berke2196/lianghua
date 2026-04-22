import React from 'react';
import ReactDOM from 'react-dom/client';
import App, { prefixReady } from './App';

prefixReady.then(() => {
  const root = ReactDOM.createRoot(document.getElementById('root'));
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
});

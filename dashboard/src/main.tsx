import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import './strategy04.css';
import Strategy04Dashboard from './Strategy04Dashboard';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Strategy04Dashboard />
  </StrictMode>,
);

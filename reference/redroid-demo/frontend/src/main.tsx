import { createRoot } from 'react-dom/client';
import App from './App';
import NativeMonitor from './NativeMonitor';
import './styles.css';

createRoot(document.getElementById('root')!).render(window.location.pathname === '/native' ? <NativeMonitor /> : <App />);

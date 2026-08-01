import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AppProvider } from './context/AppContext';
import { Navbar } from './components/layout/Navbar';
import { LandingPage } from './pages/LandingPage';
import { ChatPage } from './pages/ChatPage';

function App() {
  return (
    <AppProvider>
      <Router>
        <div className="flex flex-col min-h-screen bg-zinc-950 text-zinc-300">
          <Navbar />
          <div className="flex-1 flex flex-col">
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/chat" element={<ChatPage />} />
            </Routes>
          </div>
          <Toaster position="top-right" theme="dark" closeButton />
        </div>
      </Router>
    </AppProvider>
  );
}

export default App;

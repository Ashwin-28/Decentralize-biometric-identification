import React, { useState, useEffect } from "react";
import { Routes, Route, Link, useLocation } from "react-router-dom";
import "./App.css";

// Pages
import Home from "./pages/Home";
import Enroll from "./pages/Enroll";
import Authenticate from "./pages/Authenticate";
import Dashboard from "./pages/Dashboard";
import About from "./pages/About";
import BlockchainExplorer from "./pages/BlockchainExplorer";
import ZKPAuthentication from "./pages/ZKPAuthentication";
import MultimodalAuth from "./pages/MultimodalAuth";
import FaceVoiceAuth from "./pages/FaceVoiceAuth";
import DAOGovernance from "./pages/DAOGovernance";

// API
import { getBlockchainStatus } from "./services/api";

function App() {
  const [blockchainStatus, setBlockchainStatus] = useState({
    connected: false,
  });
  const [isScrolled, setIsScrolled] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const status = await getBlockchainStatus();
        setBlockchainStatus(status);
      } catch (error) {
        console.error("Blockchain status check failed:", error);
      }
    };

    checkStatus();
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 50);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div className="app">
      {/* Navigation */}
      <nav className={`navbar ${isScrolled ? "scrolled" : ""}`}>
        <div className="container navbar-inner">
          <Link to="/" className="brand">
            <span className="brand-name">Biometric Identity</span>
            <span className="brand-tagline">Blockchain Verified</span>
          </Link>

          <div className="nav-links">
            <Link
              to="/"
              className={`nav-link ${location.pathname === "/" ? "active" : ""}`}
            >
              Home
            </Link>
            <Link
              to="/enroll"
              className={`nav-link ${location.pathname === "/enroll" ? "active" : ""}`}
            >
              Enroll
            </Link>
            <Link
              to="/authenticate"
              className={`nav-link ${location.pathname === "/authenticate" ? "active" : ""}`}
            >
              Verify
            </Link>
            <Link
              to="/zkp-auth"
              className={`nav-link ${location.pathname === "/zkp-auth" ? "active" : ""}`}
            >
              ZKP Auth
            </Link>
            <Link
              to="/multimodal"
              className={`nav-link ${location.pathname === "/multimodal" ? "active" : ""}`}
            >
              Multimodal
            </Link>
            <Link
              to="/face-voice"
              className={`nav-link ${location.pathname === "/face-voice" ? "active" : ""}`}
            >
              Face+Voice
            </Link>
            <Link
              to="/dao"
              className={`nav-link ${location.pathname === "/dao" ? "active" : ""}`}
            >
              DAO
            </Link>
            <Link
              to="/dashboard"
              className={`nav-link ${location.pathname === "/dashboard" ? "active" : ""}`}
            >
              Dashboard
            </Link>
            <Link
              to="/blockchain"
              className={`nav-link ${location.pathname === "/blockchain" ? "active" : ""}`}
            >
              Blockchain
            </Link>
            <Link
              to="/about"
              className={`nav-link ${location.pathname === "/about" ? "active" : ""}`}
            >
              About
            </Link>
          </div>

          <div className="status-pill">
            <span
              className={`status-dot ${blockchainStatus.connected ? "" : "offline"}`}
            ></span>
            <span>
              {blockchainStatus.connected ? "Connected" : "Local Mode"}
            </span>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/enroll" element={<Enroll />} />
          <Route path="/authenticate" element={<Authenticate />} />
          <Route path="/zkp-auth" element={<ZKPAuthentication />} />
          <Route path="/multimodal" element={<MultimodalAuth />} />
          <Route path="/face-voice" element={<FaceVoiceAuth />} />
          <Route path="/dao" element={<DAOGovernance />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/blockchain" element={<BlockchainExplorer />} />
          <Route path="/about" element={<About />} />
          {/* Dummy routes to silence invasive browser tracking extensions (Copilot/ZybTracker/etc) */}
          <Route path="/hybridaction/*" element={<div style={{ display: 'none' }} />} />
          <Route path="/zybTracker/*" element={<div style={{ display: 'none' }} />} />
          <Route path="/tracker/*" element={<div style={{ display: 'none' }} />} />
          <Route path="/telemetry/*" element={<div style={{ display: 'none' }} />} />
          <Route path="/api/stats/track" element={<div style={{ display: 'none' }} />} />
          <Route path="*" element={<Home />} />
        </Routes>
      </main>

      {/* Footer */}
      <footer className="footer">
        <div className="container">
          <div className="footer-content">
            <div className="footer-brand">
              <h3>Biometric Identity</h3>
              <p className="text-muted">
                Decentralized identity verification powered by AI and blockchain
                technology.
              </p>
            </div>
            <div className="footer-links-group">
              <h4>Navigation</h4>
              <Link to="/">Home</Link>
              <Link to="/enroll">Enrollment</Link>
              <Link to="/authenticate">Verification</Link>
            </div>
            <div className="footer-links-group">
              <h4>Resources</h4>
              <Link to="/dashboard">Dashboard</Link>
              <Link to="/about">About</Link>
            </div>
          </div>
          <div className="footer-bottom">
            <p>
              © {new Date().getFullYear()} Biometric Identity Protocol. All
              rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;

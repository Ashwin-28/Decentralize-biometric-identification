import React from 'react';
import { Link } from 'react-router-dom';
import './Home.css';

function Home() {
  return (
    <div className="page home-page">
      {/* Hero Section */}
      <section className="hero">
        <div className="container">
          <div className="hero-content fade-up">
            <span className="mono-label">Decentralized Identity Protocol</span>
            <h1>
              Biometric Identity<br />
              <span className="serif-italic text-gold">Verified on Blockchain</span>
            </h1>
            <p className="hero-description">
              A privacy-preserving identity verification system combining AI-powered 
              biometric recognition with the immutability of blockchain technology.
            </p>
            <div className="hero-actions">
              <Link to="/enroll" className="btn btn-primary">
                Begin Enrollment
              </Link>
              <Link to="/authenticate" className="btn btn-outline">
                Verify Identity
              </Link>
            </div>
          </div>
          
          <div className="hero-visual">
            <div className="hero-orb"></div>
            <div className="hero-grid"></div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="features">
        <div className="container">
          <div className="section-header text-center">
            <span className="mono-label">Core Technology</span>
            <h2>Privacy-First Architecture</h2>
          </div>
          
          <div className="features-grid">
            <div className="feature-card card">
              <div className="feature-icon">🔐</div>
              <h3>Fuzzy Commitment</h3>
              <p>
                Your biometrics are never stored. Only cryptographic commitments 
                are recorded, enabling verification without exposure.
              </p>
            </div>
            
            <div className="feature-card card">
              <div className="feature-icon">⛓️</div>
              <h3>Blockchain Immutability</h3>
              <p>
                Identity records are permanently anchored on Ethereum, 
                preventing tampering and ensuring auditability.
              </p>
            </div>
            
            <div className="feature-card card">
              <div className="feature-icon">🤖</div>
              <h3>AI Recognition</h3>
              <p>
                CNN-based facial recognition with liveness detection 
                ensures accurate and spoof-resistant authentication.
              </p>
            </div>
            
            <div className="feature-card card">
              <div className="feature-icon">👤</div>
              <h3>Self-Sovereign</h3>
              <p>
                You control your identity. No central authority holds 
                your biometric data or can revoke your credentials.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="how-it-works">
        <div className="container">
          <div className="section-header text-center">
            <span className="mono-label">Process</span>
            <h2>How It Works</h2>
          </div>
          
          <div className="steps">
            <div className="step">
              <div className="step-number">01</div>
              <h4>Capture</h4>
              <p>Your biometric is captured securely via webcam</p>
            </div>
            <div className="step-connector"></div>
            <div className="step">
              <div className="step-number">02</div>
              <h4>Process</h4>
              <p>AI extracts unique features and creates a commitment</p>
            </div>
            <div className="step-connector"></div>
            <div className="step">
              <div className="step-number">03</div>
              <h4>Anchor</h4>
              <p>Cryptographic hash is recorded on the blockchain</p>
            </div>
            <div className="step-connector"></div>
            <div className="step">
              <div className="step-number">04</div>
              <h4>Verify</h4>
              <p>Future authentications are verified against the commitment</p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="cta">
        <div className="container">
          <div className="cta-card card-glass text-center">
            <span className="mono-label">Get Started</span>
            <h2>Ready to Own Your Identity?</h2>
            <p>
              Join the decentralized identity revolution. Enroll your biometrics 
              securely and take control of your digital presence.
            </p>
            <Link to="/enroll" className="btn btn-primary">
              Start Enrollment
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

export default Home;

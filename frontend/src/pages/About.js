import React from 'react';
import './About.css';

function About() {
  return (
    <div className="page about-page">
      <div className="container">
        <div className="page-header text-center">
          <span className="mono-label">Philosophy & Technology</span>
          <h1>About the System</h1>
          <p className="text-muted">
            Understanding decentralized biometric identity verification
          </p>
        </div>

        {/* Overview */}
        <section className="about-section">
          <div className="section-content">
            <h2>The Problem</h2>
            <p>
              Traditional identity systems rely on centralized databases that store 
              sensitive biometric data. These systems create single points of failure, 
              are vulnerable to massive data breaches, and give individuals no control 
              over their own identity information.
            </p>
            <p>
              When a centralized biometric database is compromised, the damage is 
              permanent—unlike passwords, you cannot change your fingerprints or face.
            </p>
          </div>
        </section>

        <div className="gold-line"></div>

        {/* Solution */}
        <section className="about-section">
          <div className="section-content">
            <h2>Our Solution</h2>
            <p>
              We combine three powerful technologies to create a truly decentralized, 
              privacy-preserving identity system:
            </p>
            
            <div className="tech-cards">
              <div className="tech-card card">
                <h4>🔐 Fuzzy Commitment Scheme</h4>
                <p>
                  A cryptographic protocol that allows biometric matching without 
                  ever storing the actual biometric template. Your biometrics are 
                  converted into a cryptographic commitment that can verify identity 
                  but cannot be reversed to reveal the original data.
                </p>
              </div>
              
              <div className="tech-card card">
                <h4>⛓️ Blockchain Technology</h4>
                <p>
                  The cryptographic commitment is stored on the Ethereum blockchain, 
                  providing immutable, tamper-proof records. No single entity controls 
                  the identity database—it's distributed across thousands of nodes worldwide.
                </p>
              </div>
              
              <div className="tech-card card">
                <h4>🤖 AI-Powered Recognition</h4>
                <p>
                  Convolutional Neural Networks extract unique biometric features 
                  with high accuracy. Liveness detection prevents spoofing attacks, 
                  ensuring that authentication requests come from real, live individuals.
                </p>
              </div>
            </div>
          </div>
        </section>

        <div className="gold-line"></div>

        {/* How FCS Works */}
        <section className="about-section">
          <div className="section-content">
            <h2>How Fuzzy Commitment Works</h2>
            
            <div className="fcs-steps">
              <div className="fcs-step">
                <div className="fcs-step-header">
                  <span className="fcs-step-num">1</span>
                  <h4>Enrollment</h4>
                </div>
                <p>
                  A random secret key <code>K</code> is generated. This key is encoded 
                  using an error-correcting code to produce a codeword <code>C</code>. 
                  The codeword is XORed with your biometric template <code>x</code> to 
                  produce an offset <code>δ = x ⊕ C</code>.
                </p>
                <p>
                  Only <code>h(K)</code> (hash of the key) and <code>δ</code> are stored 
                  on the blockchain. Neither reveals your actual biometric.
                </p>
              </div>
              
              <div className="fcs-step">
                <div className="fcs-step-header">
                  <span className="fcs-step-num">2</span>
                  <h4>Authentication</h4>
                </div>
                <p>
                  When you authenticate, a new biometric <code>x'</code> is captured. 
                  The system computes <code>C' = x' ⊕ δ</code>. If your new biometric 
                  is close enough to the original, the error-correcting code can decode 
                  <code>C'</code> to recover the original key <code>K</code>.
                </p>
                <p>
                  If <code>h(K') = h(K)</code>, authentication succeeds. The beauty is 
                  that minor biometric variations are tolerated, but the original 
                  template is never exposed.
                </p>
              </div>
            </div>
          </div>
        </section>

        <div className="gold-line"></div>

        {/* References */}
        <section className="about-section">
          <div className="section-content">
            <h2>Academic Foundation</h2>
            <p>This system is built on peer-reviewed research:</p>
            
            <ul className="references">
              <li>
                <strong>"A Fuzzy Commitment Scheme"</strong> — Juels & Wattenberg (1999)
                <br />
                <span className="text-muted">Foundation of biometric template protection</span>
              </li>
              <li>
                <strong>"BiometricIdentity dApp"</strong> — SoftwareX (2024)
                <br />
                <span className="text-muted">Decentralized authentication architecture</span>
              </li>
              <li>
                <strong>"BioZero: Privacy-Preserving Biometric Authentication"</strong> — arXiv (2024)
                <br />
                <span className="text-muted">Zero-knowledge proofs for biometrics</span>
              </li>
            </ul>
          </div>
        </section>
      </div>
    </div>
  );
}

export default About;

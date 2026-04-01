import React, { useState, useEffect } from 'react';
import { getStats, getBlockchainStatus, getSubjects, getAuthLogs } from '../services/api';
import './Dashboard.css';

function Dashboard() {
  const [stats, setStats] = useState(null);
  const [blockchainInfo, setBlockchainInfo] = useState(null);
  const [subjects, setSubjects] = useState([]);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('subjects');
  const [copyFeedback, setCopyFeedback] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsData, blockchainData, subjectsData, logsData] = await Promise.all([
          getStats(),
          getBlockchainStatus(),
          getSubjects(),
          getAuthLogs()
        ]);
        setStats(statsData);
        setBlockchainInfo(blockchainData);
        setSubjects(subjectsData.subjects || []);
        setLogs(logsData.logs || []);
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopyFeedback(text);
    setTimeout(() => setCopyFeedback(null), 2000);
  };

  return (
    <div className="page dashboard-page">
      <div className="container">
        <div className="page-header text-center">
          <span className="mono-label">System Analytics</span>
          <h1>Dashboard</h1>
          <p className="text-muted">
            Real-time blockchain and system metrics
          </p>
        </div>

        {loading ? (
          <div className="loading-state text-center">
            <div className="loading-spinner"></div>
            <p>Loading dashboard data...</p>
          </div>
        ) : (
          <>
            {/* Stats Cards */}
            <div className="stats-grid">
              <div className="stat-card card">
                <span className="stat-label">Total Subjects</span>
                <span className="stat-value">{stats?.total_subjects || 0}</span>
                <span className="stat-desc">Enrolled identities</span>
              </div>
              
              <div className="stat-card card">
                <span className="stat-label">ML Models</span>
                <span className="stat-value">{stats?.models_trained || 0}</span>
                <span className="stat-desc">Trained Models</span>
              </div>
              
              <div className="stat-card card">
                <span className="stat-label">Auth Records</span>
                <span className="stat-value">{stats?.total_authentications || stats?.total_auth_records || 0}</span>
                <span className="stat-desc">Verification attempts</span>
              </div>
              
              <div className="stat-card card">
                <span className="stat-label">Current Block</span>
                <span className="stat-value">{stats?.current_block || '—'}</span>
                <span className="stat-desc">Blockchain height</span>
              </div>
            </div>

            {/* Blockchain Status */}
            <div className="blockchain-section">
              <h2>System Status</h2>
              <div className="blockchain-card card">
                <div className="blockchain-grid">
                  <div className="bc-item">
                    <span className="bc-label">Blockchain</span>
                    <span className={`bc-value ${blockchainInfo?.connected ? 'connected' : 'disconnected'}`}>
                      {blockchainInfo?.connected ? '● Connected' : '○ Disconnected'}
                    </span>
                  </div>
                  
                  <div className="bc-item">
                    <span className="bc-label">Database</span>
                    <span className={`bc-value ${stats?.database_connected ? 'connected' : 'disconnected'}`}>
                      {stats?.database_connected ? '● Connected' : '○ Disconnected'}
                    </span>
                  </div>
                  
                  <div className="bc-item">
                    <span className="bc-label">Gas Price</span>
                    <span className="bc-value">
                      {blockchainInfo?.gas_price 
                        ? `${(parseInt(blockchainInfo.gas_price) / 1e9).toFixed(2)} Gwei`
                        : '—'}
                    </span>
                  </div>
                  
                  <div className="bc-item">
                    <span className="bc-label">Contract Address</span>
                    <span className="bc-value mono">
                      {blockchainInfo?.contract_address 
                        ? `${blockchainInfo.contract_address.slice(0, 10)}...${blockchainInfo.contract_address.slice(-8)}`
                        : 'Not deployed'}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Database Explorer Section */}
            <div className="db-section">
              <div className="section-header">
                <h2>Database Explorer</h2>
                <div className="tabs">
                  <button 
                    className={`tab-btn ${activeTab === 'subjects' ? 'active' : ''}`}
                    onClick={() => setActiveTab('subjects')}
                  >
                    Subjects
                  </button>
                  <button 
                    className={`tab-btn ${activeTab === 'logs' ? 'active' : ''}`}
                    onClick={() => setActiveTab('logs')}
                  >
                    Authentication Logs
                  </button>
                </div>
              </div>

              <div className="db-content card">
                {activeTab === 'subjects' ? (
                  <div className="table-responsive">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Name</th>
                          <th>Human Code</th>
                          <th>Subject ID (Hash)</th>
                          <th>Type</th>
                          <th>Created At</th>
                        </tr>
                      </thead>
                      <tbody>
                        {subjects.length > 0 ? subjects.map(sub => (
                          <tr key={sub.id}>
                            <td>{sub.id}</td>
                            <td>{sub.name}</td>
                            <td className="mono accent-text">
                              {sub.subject_code || 'N/A'}
                            </td>
                            <td className="mono">
                              <span className="hash-preview">
                                {sub.subject_id?.slice(0, 16)}...
                              </span>
                              <button 
                                className="copy-btn"
                                onClick={() => copyToClipboard(sub.subject_id)}
                                title="Copy full ID"
                              >
                                {copyFeedback === sub.subject_id ? '✓' : '📋'}
                              </button>
                            </td>
                            <td>{sub.biometric_type}</td>
                            <td>{new Date(sub.created_at).toLocaleString()}</td>
                          </tr>
                        )) : (
                          <tr><td colSpan="6" className="text-center">No subjects found</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="table-responsive">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Subject ID</th>
                          <th>Status</th>
                          <th>Timestamp</th>
                        </tr>
                      </thead>
                      <tbody>
                        {logs.length > 0 ? logs.map(log => (
                          <tr key={log.id}>
                            <td>{log.id}</td>
                            <td className="mono">{log.subject_id?.slice(0, 16)}...</td>
                            <td>
                              <span className={`status-badge ${log.success ? 'success' : 'failure'}`}>
                                {log.success ? 'Success' : 'Failed'}
                              </span>
                            </td>
                            <td>{new Date(log.created_at).toLocaleString()}</td>
                          </tr>
                        )) : (
                          <tr><td colSpan="4" className="text-center">No logs found</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>

            {/* System Info */}
            <div className="system-section">
              <h2>System Information</h2>
              <div className="system-grid">
                <div className="system-card card">
                  <div className="system-icon">🔐</div>
                  <h4>Encryption</h4>
                  <p>AES-256-GCM</p>
                </div>
                <div className="system-card card">
                  <div className="system-icon">🧬</div>
                  <h4>Biometric Engine</h4>
                  <p>CNN (TensorFlow) + FaceRec</p>
                </div>
                <div className="system-card card">
                  <div className="system-icon">🔗</div>
                  <h4>Commitment Scheme</h4>
                  <p>Fuzzy Commitment (FCS)</p>
                </div>
                <div className="system-card card">
                  <div className="system-icon">💾</div>
                  <h4>Storage</h4>
                  <p>SQLAlchemy + IPFS</p>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default Dashboard;

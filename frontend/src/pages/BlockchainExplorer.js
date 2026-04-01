import React, { useState, useEffect, useCallback } from "react";
import { getBlockchainData, getBlockchainStatus } from "../services/api";
import "./BlockchainExplorer.css";

const BlockchainExplorer = () => {
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState(null);
  const [blocks, setBlocks] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [selectedBlock, setSelectedBlock] = useState(null);
  const [selectedTx, setSelectedTx] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [statusData, blockchainData] = await Promise.all([
        getBlockchainStatus(),
        getBlockchainData(),
      ]);
      setStatus(statusData);
      if (blockchainData) {
        setBlocks(blockchainData.blocks || []);
        setTransactions(blockchainData.transactions || []);
        setAccounts(blockchainData.accounts || []);
      }
    } catch (error) {
      console.error("Error fetching blockchain data:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    let interval;
    if (autoRefresh) {
      interval = setInterval(fetchData, 5000);
    }
    return () => clearInterval(interval);
  }, [fetchData, autoRefresh]);

  const formatAddress = (addr) => {
    if (!addr) return "N/A";
    return `${addr.slice(0, 8)}...${addr.slice(-6)}`;
  };

  const formatEther = (wei) => {
    if (!wei) return "0";
    const eth = parseFloat(wei) / 1e18;
    return eth.toFixed(4);
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return "N/A";
    return new Date(timestamp * 1000).toLocaleString();
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  if (loading) {
    return (
      <div className="explorer-loading">
        <div className="loading-spinner"></div>
        <p>Connecting to blockchain...</p>
      </div>
    );
  }

  return (
    <div className="blockchain-explorer">
      {/* Header */}
      <div className="explorer-header">
        <div className="header-content">
          <h1>
            <span className="icon">⛓️</span> Blockchain Explorer
          </h1>
          <p>Real-time visualization of your local Ganache blockchain</p>
        </div>
        <div className="header-controls">
          <label className="auto-refresh">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            Auto-refresh
          </label>
          <button className="refresh-btn" onClick={fetchData}>
            🔄 Refresh
          </button>
        </div>
      </div>

      {/* Network Status Cards */}
      <div className="status-cards">
        <div
          className={`status-card ${status?.connected ? "connected" : "disconnected"}`}
        >
          <div className="card-icon">🌐</div>
          <div className="card-content">
            <span className="card-label">Network Status</span>
            <span className="card-value">
              {status?.connected ? "Connected" : "Disconnected"}
            </span>
          </div>
          <div
            className={`status-indicator ${status?.connected ? "online" : "offline"}`}
          ></div>
        </div>

        <div className="status-card">
          <div className="card-icon">📦</div>
          <div className="card-content">
            <span className="card-label">Block Height</span>
            <span className="card-value">{status?.block_number || 0}</span>
          </div>
        </div>

        <div className="status-card">
          <div className="card-icon">🔗</div>
          <div className="card-content">
            <span className="card-label">Network ID</span>
            <span className="card-value">{status?.network_id || "N/A"}</span>
          </div>
        </div>

        <div className="status-card">
          <div className="card-icon">⛽</div>
          <div className="card-content">
            <span className="card-label">Gas Price</span>
            <span className="card-value">
              {status?.gas_price
                ? `${(parseInt(status.gas_price) / 1e9).toFixed(2)} Gwei`
                : "N/A"}
            </span>
          </div>
        </div>
      </div>

      {/* Contract Info */}
      {status?.contract_address && (
        <div className="contract-banner">
          <span className="contract-label">📜 Smart Contract:</span>
          <code className="contract-address">{status.contract_address}</code>
          <button
            className="copy-btn"
            onClick={() => copyToClipboard(status.contract_address)}
            title="Copy address"
          >
            📋
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="explorer-tabs">
        <button
          className={`tab ${activeTab === "overview" ? "active" : ""}`}
          onClick={() => setActiveTab("overview")}
        >
          📊 Overview
        </button>
        <button
          className={`tab ${activeTab === "blocks" ? "active" : ""}`}
          onClick={() => setActiveTab("blocks")}
        >
          📦 Blocks ({blocks.length})
        </button>
        <button
          className={`tab ${activeTab === "transactions" ? "active" : ""}`}
          onClick={() => setActiveTab("transactions")}
        >
          💸 Transactions ({transactions.length})
        </button>
        <button
          className={`tab ${activeTab === "accounts" ? "active" : ""}`}
          onClick={() => setActiveTab("accounts")}
        >
          👛 Accounts ({accounts.length})
        </button>
      </div>

      {/* Tab Content */}
      <div className="tab-content">
        {/* Overview Tab */}
        {activeTab === "overview" && (
          <div className="overview-tab">
            <div className="overview-grid">
              {/* Recent Blocks */}
              <div className="overview-section">
                <h3>📦 Recent Blocks</h3>
                <div className="mini-list">
                  {blocks.slice(0, 5).map((block) => (
                    <div
                      key={block.number}
                      className="mini-item"
                      onClick={() => {
                        setSelectedBlock(block);
                        setActiveTab("blocks");
                      }}
                    >
                      <span className="block-number">#{block.number}</span>
                      <span className="block-txs">
                        {block.transactions?.length || 0} txs
                      </span>
                      <span className="block-time">
                        {formatTimestamp(block.timestamp)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Recent Transactions */}
              <div className="overview-section">
                <h3>💸 Recent Transactions</h3>
                <div className="mini-list">
                  {transactions.slice(0, 5).map((tx, idx) => (
                    <div
                      key={tx.hash || idx}
                      className="mini-item tx-item"
                      onClick={() => {
                        setSelectedTx(tx);
                        setActiveTab("transactions");
                      }}
                    >
                      <span className="tx-hash">{formatAddress(tx.hash)}</span>
                      <span className="tx-arrow">→</span>
                      <span className="tx-to">{formatAddress(tx.to)}</span>
                      <span className="tx-value">
                        {formatEther(tx.value)} ETH
                      </span>
                    </div>
                  ))}
                  {transactions.length === 0 && (
                    <p className="no-data">No transactions yet</p>
                  )}
                </div>
              </div>
            </div>

            {/* Blockchain Visualization */}
            <div className="blockchain-visual">
              <h3>🔗 Blockchain Visualization</h3>
              <div className="chain-container">
                {blocks.slice(0, 10).map((block, idx) => (
                  <React.Fragment key={block.number}>
                    <div
                      className={`block-node ${selectedBlock?.number === block.number ? "selected" : ""}`}
                      onClick={() => setSelectedBlock(block)}
                    >
                      <div className="block-header">Block #{block.number}</div>
                      <div className="block-body">
                        <div className="block-stat">
                          <span>Txs:</span> {block.transactions?.length || 0}
                        </div>
                        <div className="block-stat">
                          <span>Gas:</span> {block.gasUsed || 0}
                        </div>
                      </div>
                      <div className="block-hash" title={block.hash}>
                        {formatAddress(block.hash)}
                      </div>
                    </div>
                    {idx < Math.min(blocks.length - 1, 9) && (
                      <div className="chain-link">🔗</div>
                    )}
                  </React.Fragment>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Blocks Tab */}
        {activeTab === "blocks" && (
          <div className="blocks-tab">
            <div className="blocks-list">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Block</th>
                    <th>Hash</th>
                    <th>Transactions</th>
                    <th>Gas Used</th>
                    <th>Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {blocks.map((block) => (
                    <tr
                      key={block.number}
                      className={
                        selectedBlock?.number === block.number ? "selected" : ""
                      }
                      onClick={() => setSelectedBlock(block)}
                    >
                      <td className="block-num">#{block.number}</td>
                      <td className="hash-cell">
                        <code>{formatAddress(block.hash)}</code>
                        <button
                          className="copy-btn small"
                          onClick={(e) => {
                            e.stopPropagation();
                            copyToClipboard(block.hash);
                          }}
                        >
                          📋
                        </button>
                      </td>
                      <td>{block.transactions?.length || 0}</td>
                      <td>{block.gasUsed?.toLocaleString() || 0}</td>
                      <td>{formatTimestamp(block.timestamp)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Block Details */}
            {selectedBlock && (
              <div className="detail-panel">
                <h3>Block #{selectedBlock.number} Details</h3>
                <div className="detail-grid">
                  <div className="detail-item">
                    <span className="label">Hash:</span>
                    <code>{selectedBlock.hash}</code>
                  </div>
                  <div className="detail-item">
                    <span className="label">Parent Hash:</span>
                    <code>{selectedBlock.parentHash}</code>
                  </div>
                  <div className="detail-item">
                    <span className="label">Miner:</span>
                    <code>{selectedBlock.miner}</code>
                  </div>
                  <div className="detail-item">
                    <span className="label">Gas Limit:</span>
                    <span>{selectedBlock.gasLimit?.toLocaleString()}</span>
                  </div>
                  <div className="detail-item">
                    <span className="label">Gas Used:</span>
                    <span>{selectedBlock.gasUsed?.toLocaleString()}</span>
                  </div>
                  <div className="detail-item">
                    <span className="label">Timestamp:</span>
                    <span>{formatTimestamp(selectedBlock.timestamp)}</span>
                  </div>
                </div>
                <button
                  className="close-btn"
                  onClick={() => setSelectedBlock(null)}
                >
                  ✕ Close
                </button>
              </div>
            )}
          </div>
        )}

        {/* Transactions Tab */}
        {activeTab === "transactions" && (
          <div className="transactions-tab">
            <div className="transactions-list">
              {transactions.length > 0 ? (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Tx Hash</th>
                      <th>Block</th>
                      <th>From</th>
                      <th>To</th>
                      <th>Value</th>
                      <th>Gas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((tx, idx) => (
                      <tr
                        key={tx.hash || idx}
                        className={
                          selectedTx?.hash === tx.hash ? "selected" : ""
                        }
                        onClick={() => setSelectedTx(tx)}
                      >
                        <td className="hash-cell">
                          <code>{formatAddress(tx.hash)}</code>
                        </td>
                        <td>#{tx.blockNumber}</td>
                        <td>
                          <code>{formatAddress(tx.from)}</code>
                        </td>
                        <td>
                          <code>
                            {tx.to ? formatAddress(tx.to) : "Contract Creation"}
                          </code>
                        </td>
                        <td>{formatEther(tx.value)} ETH</td>
                        <td>{tx.gas?.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="no-transactions">
                  <span className="icon">📭</span>
                  <h3>No Transactions Yet</h3>
                  <p>
                    Transactions will appear here when you enroll or verify
                    identities.
                  </p>
                </div>
              )}
            </div>

            {/* Transaction Details */}
            {selectedTx && (
              <div className="detail-panel">
                <h3>Transaction Details</h3>
                <div className="detail-grid">
                  <div className="detail-item full">
                    <span className="label">Transaction Hash:</span>
                    <code>{selectedTx.hash}</code>
                  </div>
                  <div className="detail-item">
                    <span className="label">Status:</span>
                    <span className="status-badge success">✓ Success</span>
                  </div>
                  <div className="detail-item">
                    <span className="label">Block:</span>
                    <span>#{selectedTx.blockNumber}</span>
                  </div>
                  <div className="detail-item full">
                    <span className="label">From:</span>
                    <code>{selectedTx.from}</code>
                  </div>
                  <div className="detail-item full">
                    <span className="label">To:</span>
                    <code>{selectedTx.to || "Contract Creation"}</code>
                  </div>
                  <div className="detail-item">
                    <span className="label">Value:</span>
                    <span>{formatEther(selectedTx.value)} ETH</span>
                  </div>
                  <div className="detail-item">
                    <span className="label">Gas Used:</span>
                    <span>{selectedTx.gas?.toLocaleString()}</span>
                  </div>
                  <div className="detail-item">
                    <span className="label">Gas Price:</span>
                    <span>
                      {(parseInt(selectedTx.gasPrice || 0) / 1e9).toFixed(2)}{" "}
                      Gwei
                    </span>
                  </div>
                  {selectedTx.input && selectedTx.input !== "0x" && (
                    <div className="detail-item full">
                      <span className="label">Input Data:</span>
                      <code className="input-data">
                        {selectedTx.input.slice(0, 66)}...
                      </code>
                    </div>
                  )}
                </div>
                <button
                  className="close-btn"
                  onClick={() => setSelectedTx(null)}
                >
                  ✕ Close
                </button>
              </div>
            )}
          </div>
        )}

        {/* Accounts Tab */}
        {activeTab === "accounts" && (
          <div className="accounts-tab">
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Address</th>
                  <th>Balance (ETH)</th>
                  <th>Tx Count</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((account, idx) => (
                  <tr key={account.address}>
                    <td>{idx}</td>
                    <td className="hash-cell">
                      <code>{account.address}</code>
                      <button
                        className="copy-btn small"
                        onClick={() => copyToClipboard(account.address)}
                      >
                        📋
                      </button>
                    </td>
                    <td className="balance">
                      {formatEther(account.balance)} ETH
                    </td>
                    <td>{account.txCount || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default BlockchainExplorer;

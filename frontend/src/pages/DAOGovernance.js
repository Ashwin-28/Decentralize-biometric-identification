import React, { useState } from 'react';
import './DAOGovernance.css';

const DAOGovernance = () => {
    const [userTokens] = useState(1250);
    const [proposals, setProposals] = useState([
        {
            id: 1,
            title: "Upgrade Biometric Engine to V2.1",
            description: "Implementation of advanced noise cancellation for voice prints and improved low-light facial recognition accuracy.",
            status: "Active",
            votesFor: 45200,
            votesAgainst: 12100,
            expiryDate: "2026-02-15",
            author: "0x742d...44e",
            hasVoted: false
        },
        {
            id: 2,
            title: "Integrate Layer 2 Scaling (Arbitrum)",
            description: "Reducing transaction costs for identity verification by migrating state commits to Arbitrum Nitro.",
            status: "Active",
            votesFor: 89000,
            votesAgainst: 5400,
            expiryDate: "2026-01-28",
            author: "0xde0b...123",
            hasVoted: true
        },
        {
            id: 3,
            title: "Expand Validator Node Incentive Program",
            description: "Increasing monthly BIO token rewards for certified biometric validator nodes by 15%.",
            status: "Executed",
            votesFor: 120000,
            votesAgainst: 15000,
            expiryDate: "2026-01-10",
            author: "0x3f5c...a1b",
            hasVoted: false
        }
    ]);

    const handleVote = (id, type) => {
        setProposals(proposals.map(p => {
            if (p.id === id) {
                return {
                    ...p,
                    votesFor: type === 'for' ? p.votesFor + userTokens : p.votesFor,
                    votesAgainst: type === 'against' ? p.votesAgainst + userTokens : p.votesAgainst,
                    hasVoted: true
                };
            }
            return p;
        }));
    };

    return (
        <div className="dao-container">
            <div className="dao-header">
                <div>
                    <h1>🏛️ DAO Governance</h1>
                    <p>Participate in the future of the Biometric Identity Protocol.</p>
                </div>
                <div className="user-stats glass">
                    <div className="stat">
                        <span className="label">Your BIO Balance</span>
                        <span className="value">{userTokens.toLocaleString()} BIO</span>
                    </div>
                    <div className="stat">
                        <span className="label">Voting Power</span>
                        <span className="value">{(userTokens / 1000000 * 100).toFixed(4)}%</span>
                    </div>
                </div>
            </div>

            <div className="dao-summary">
                <div className="summary-card glass">
                    <span className="label">Total Treasury</span>
                    <span className="value gold">$2.4M USD</span>
                    <div className="trend up">+4.2%</div>
                </div>
                <div className="summary-card glass">
                    <span className="label">Active Proposals</span>
                    <span className="value">2</span>
                </div>
                <div className="summary-card glass">
                    <span className="label">Total BIO Staked</span>
                    <span className="value">8.4M</span>
                </div>
            </div>

            <div className="main-content">
                <div className="proposals-section">
                    <div className="section-header">
                        <h2>Active Proposals</h2>
                        <button className="btn-secondary">Create Proposal</button>
                    </div>

                    <div className="proposal-list">
                        {proposals.map(p => (
                            <div key={p.id} className={`proposal-card glass ${p.status.toLowerCase()}`}>
                                <div className="card-header">
                                    <span className={`status-pill ${p.status.toLowerCase()}`}>{p.status}</span>
                                    <span className="expiry">Ends: {p.expiryDate}</span>
                                </div>
                                <div className="card-body">
                                    <h3>{p.title}</h3>
                                    <p className="description">{p.description}</p>
                                    <div className="author">Propounded by: {p.author}</div>
                                </div>
                                <div className="voting-stats">
                                    <div className="votes">
                                        <div className="vote-label">
                                            <span>For: {p.votesFor.toLocaleString()}</span>
                                            <span>{(p.votesFor / (p.votesFor + p.votesAgainst) * 100).toFixed(1)}%</span>
                                        </div>
                                        <div className="progress-bar">
                                            <div
                                                className="fill for"
                                                style={{ width: `${(p.votesFor / (p.votesFor + p.votesAgainst) * 100)}%` }}
                                            ></div>
                                        </div>
                                    </div>
                                    <div className="votes">
                                        <div className="vote-label">
                                            <span>Against: {p.votesAgainst.toLocaleString()}</span>
                                            <span>{(p.votesAgainst / (p.votesFor + p.votesAgainst) * 100).toFixed(1)}%</span>
                                        </div>
                                        <div className="progress-bar">
                                            <div
                                                className="fill against"
                                                style={{ width: `${(p.votesAgainst / (p.votesFor + p.votesAgainst) * 100)}%` }}
                                            ></div>
                                        </div>
                                    </div>
                                </div>
                                <div className="card-footer">
                                    {p.status === "Active" && (
                                        p.hasVoted ? (
                                            <div className="voted-message">✓ You have voted on this proposal</div>
                                        ) : (
                                            <div className="vote-actions">
                                                <button className="btn-vote for" onClick={() => handleVote(p.id, 'for')}>Vote For</button>
                                                <button className="btn-vote against" onClick={() => handleVote(p.id, 'against')}>Vote Against</button>
                                            </div>
                                        )
                                    )}
                                    {p.status === "Executed" && <div className="executed-label">Proposal fully executed on-chain</div>}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="sidebar">
                    <div className="sidebar-card glass">
                        <h3>Treasury Allocation</h3>
                        <div className="asset-list">
                            <div className="asset">
                                <div className="asset-info">
                                    <span className="dot eth"></span>
                                    <span>ETH</span>
                                </div>
                                <span>45%</span>
                            </div>
                            <div className="asset">
                                <div className="asset-info">
                                    <span className="dot usdc"></span>
                                    <span>USDC</span>
                                </div>
                                <span>35%</span>
                            </div>
                            <div className="asset">
                                <div className="asset-info">
                                    <span className="dot bio"></span>
                                    <span>BIO</span>
                                </div>
                                <span>20%</span>
                            </div>
                        </div>
                        <div className="pie-chart-mock">
                            <div className="slice" style={{ '--p': 45, '--c': '#627eea', '--b': 0 }}></div>
                            <div className="slice" style={{ '--p': 35, '--c': '#2775ca', '--b': 45 }}></div>
                            <div className="slice" style={{ '--p': 20, '--c': '#c5a059', '--b': 80 }}></div>
                        </div>
                    </div>

                    <div className="sidebar-card glass delegate">
                        <h3>Delegate Voting Power</h3>
                        <p>Not active enough to vote? Delegate your BIO power to a trusted validator.</p>
                        <input type="text" placeholder="Wallet address or ENS" className="id-input" />
                        <button className="btn-primary">Delegate Power</button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default DAOGovernance;

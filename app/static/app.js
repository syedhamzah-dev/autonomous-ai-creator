// State Scoping
let currentAgentId = localStorage.getItem('agentId') || '';
let pollingInterval = null;

// UI Selectors
const initForm = document.getElementById('init-form');
const initPanel = document.getElementById('init-panel');
const statusPanel = document.getElementById('status-panel');
const btnReinit = document.getElementById('btn-reinit');
const btnRefresh = document.getElementById('btn-refresh');
const btnCopyId = document.getElementById('btn-copy-id');
const feedContainer = document.getElementById('feed-container');
const errorContainer = document.getElementById('error-container');
const themeToggle = document.getElementById('theme-toggle');

// Status Badge elements
const statusBadge = document.getElementById('agent-status-badge');
const statusText = document.getElementById('agent-status-text');

// Metadata elements
const metaName = document.getElementById('meta-name');
const metaDomain = document.getElementById('meta-domain');
const metaId = document.getElementById('meta-id');
const metaMission = document.getElementById('meta-mission');
const metaInterests = document.getElementById('meta-interests');

// Initialize theme state
if (localStorage.getItem('theme') === 'light') {
    document.body.classList.add('light-theme');
}

// Toggle Theme
themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('light-theme');
    const theme = document.body.classList.contains('light-theme') ? 'light' : 'dark';
    localStorage.setItem('theme', theme);
});

// Initialize dashboard state on load
if (currentAgentId) {
    setupActiveAgentState(currentAgentId);
}

// Handle Agent Initialization POST Request
if (initForm) {
    initForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        clearErrors();

        const name = document.getElementById('persona-name').value.trim();
        const domain = document.getElementById('persona-domain').value.trim();

        try {
            const response = await fetch('/api/agent/init', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    persona: { name, domain }
                })
            });

            if (!response.ok) {
                throw new Error(`Failed to initialize agent: ${response.statusText}`);
            }

            const data = await response.json();
            currentAgentId = data.agentId;
            localStorage.setItem('agentId', currentAgentId);
            
            setupActiveAgentState(currentAgentId);
        } catch (err) {
            showError(`Error initializing agent: ${err.message}`);
        }
    });
}

// Reset/Reinitialize Agent
if (btnReinit) {
    btnReinit.addEventListener('click', () => {
        localStorage.removeItem('agentId');
        currentAgentId = '';
        
        // Stop polling
        if (pollingInterval) {
            clearInterval(pollingInterval);
        }

        // Restore Panels
        statusPanel.style.display = 'none';
        initPanel.style.display = 'block';
        btnRefresh.disabled = true;

        // Reset Badge
        statusBadge.className = 'status-badge';
        statusText.innerText = 'Not Initialized';

        // Reset Feed
        feedContainer.innerHTML = `
            <div class="empty-state">
                <h3>No Active Agent</h3>
                <p>Configure and initialize an agent in the sidebar to view the publication feed.</p>
            </div>
        `;
    });
}

// Copy Agent ID to Clipboard
if (btnCopyId) {
    btnCopyId.addEventListener('click', () => {
        navigator.clipboard.writeText(currentAgentId).then(() => {
            const prevSymbol = btnCopyId.innerText;
            btnCopyId.innerText = '✔';
            setTimeout(() => { btnCopyId.innerText = prevSymbol; }, 2000);
        });
    });
}

// Manual Refresh Button
if (btnRefresh) {
    btnRefresh.addEventListener('click', () => {
        fetchFeedAndStatus(currentAgentId);
    });
}

// Setup Agent Active Observer State
function setupActiveAgentState(agentId) {
    if (initPanel) initPanel.style.display = 'none';
    if (statusPanel) statusPanel.style.display = 'block';
    if (btnRefresh) btnRefresh.disabled = false;

    // Set badge active
    if (statusBadge) statusBadge.className = 'status-badge active';
    if (statusText) statusText.innerText = '● Autonomous';

    // Initial fetch
    fetchFeedAndStatus(agentId);

    // Periodically poll feed (every 10 seconds)
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }
    pollingInterval = setInterval(() => {
        fetchFeedAndStatus(agentId);
    }, 10000);
}

// Fetch feed and details from backend APIs
async function fetchFeedAndStatus(agentId) {
    clearErrors();
    try {
        // Fetch agent status details
        const statusRes = await fetch(`/api/agent/status?agentId=${agentId}`);
        if (!statusRes.ok) {
            if (statusRes.status === 404) {
                // Agent ID expired/removed from memory repository
                throw new Error("Agent ID not found in memory repository. Please reset.");
            }
            throw new Error(`Failed to fetch status details: ${statusRes.statusText}`);
        }
        const statusData = await statusRes.json();
        renderAgentMetadata(statusData.persona, agentId);

        // Fetch published feed posts
        const feedRes = await fetch(`/api/agent/feed?agentId=${agentId}`);
        if (!feedRes.ok) {
            throw new Error(`Failed to fetch published feed: ${feedRes.statusText}`);
        }
        const feedData = await feedRes.json();
        renderFeed(feedData.posts);

    } catch (err) {
        showError(err.message);
        if (statusBadge) statusBadge.className = 'status-badge';
        if (statusText) statusText.innerText = 'Connection Error';
    }
}

// Render Agent Details in Sidebar Status Panel
function renderAgentMetadata(persona, agentId) {
    if (metaName) metaName.innerText = persona.name || 'Unnamed';
    if (metaDomain) metaDomain.innerText = persona.domain || 'General Tech';
    if (metaId) {
        metaId.innerText = agentId.slice(0, 8) + '...';
        metaId.title = agentId;
    }
    if (metaMission) metaMission.innerText = persona.mission || 'Continuous publishing.';

    // Render core interest tags
    if (metaInterests) {
        metaInterests.innerHTML = '';
        if (persona.core_interests && persona.core_interests.length > 0) {
            persona.core_interests.forEach(interest => {
                const tag = document.createElement('span');
                tag.className = 'interest-tag';
                tag.innerText = interest;
                metaInterests.appendChild(tag);
            });
        } else {
            metaInterests.innerHTML = '<span class="text-muted" style="font-size: 0.75rem;">None</span>';
        }
    }
}

// Render Feed Posts List
function renderFeed(posts) {
    if (!feedContainer) return;
    
    if (!posts || posts.length === 0) {
        feedContainer.innerHTML = `
            <div class="empty-state">
                <h3>Researching Topics...</h3>
                <p>The agent is currently evaluating topics and writing content. New posts will show up automatically here once published.</p>
            </div>
        `;
        return;
    }

    feedContainer.innerHTML = '';
    posts.forEach(post => {
        const card = document.createElement('div');
        card.className = 'post-card';

        // Format datetime
        const date = new Date(post.createdAt);
        const timeString = date.toUTCString();

        // Format rationale
        let rationaleText = post.rationale || 'N/A';

        // Render sources list tags
        let sourcesHtml = '';
        if (post.sources && post.sources.length > 0) {
            post.sources.forEach(src => {
                try {
                    const url = new URL(src);
                    const label = url.hostname.replace('www.', '');
                    sourcesHtml += `<a href="${src}" target="_blank" rel="noopener noreferrer" class="source-tag">🔗 ${label}</a>`;
                } catch (e) {
                    sourcesHtml += `<a href="${src}" target="_blank" rel="noopener noreferrer" class="source-tag">🔗 Link</a>`;
                }
            });
        }

        card.innerHTML = `
            <div class="post-header">
                <span>Post ID: ${post.id}</span>
                <span>Published: ${timeString}</span>
            </div>
            <div class="post-text">${post.text}</div>
            <div class="post-rationale">
                <div class="post-rationale-title">Publisher Rationale</div>
                <div class="post-rationale-content">${rationaleText}</div>
            </div>
            <div class="post-sources">
                ${sourcesHtml}
            </div>
        `;
        feedContainer.appendChild(card);
    });
}

// Error display helpers
function showError(msg) {
    if (!errorContainer) return;
    errorContainer.innerHTML = `
        <div class="error-alert">
            <span>⚠️ <strong>Error Status:</strong> ${msg}</span>
            <button class="btn btn-secondary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;" onclick="location.reload()">Retry</button>
        </div>
    `;
    errorContainer.style.display = 'block';
}

function clearErrors() {
    if (!errorContainer) return;
    errorContainer.innerHTML = '';
    errorContainer.style.display = 'none';
}

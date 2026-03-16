/**
 * Podcast 自動解説 — クライアントアプリ
 */

const API_BASE = '';
const POLL_INTERVAL = 30_000; // 30秒ごとに更新

// --- DOM要素 ---
const dom = {
    btnScan: document.getElementById('btn-scan'),
    btnMonitor: document.getElementById('btn-monitor'),
    statusIndicator: document.getElementById('status-indicator'),
    statusBar: document.getElementById('status-bar'),
    statusText: document.getElementById('status-text'),
    statTotal: document.getElementById('stat-total'),
    statDone: document.getElementById('stat-done'),
    statProcessing: document.getElementById('stat-processing'),
    episodesList: document.getElementById('episodes-list'),
    loading: document.getElementById('loading'),
    emptyState: document.getElementById('empty-state'),
    modalOverlay: document.getElementById('modal-overlay'),
    modalClose: document.getElementById('btn-modal-close'),
    modalPodcast: document.getElementById('modal-podcast'),
    modalDate: document.getElementById('modal-date'),
    modalTitle: document.getElementById('modal-title'),
    modalStatus: document.getElementById('modal-status'),
    modalSummary: document.getElementById('modal-summary'),
    modalTranscript: document.getElementById('modal-transcript'),
};

// --- 状態 ---
let state = {
    episodes: [],
    counts: {},
    isProcessing: false,
};

// --- API ---
async function api(path, options = {}) {
    const res = await fetch(`${API_BASE}${path}`, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

async function fetchEpisodes() {
    const data = await api('/api/episodes');
    state.episodes = data.episodes;
    state.counts = data.counts;
    return data;
}

async function fetchStatus() {
    const data = await api('/api/status');
    state.isProcessing = data.processing;
    state.isMonitoring = data.is_monitoring;
    state.counts = data.counts;
    return data;
}

async function triggerScan() {
    return api('/api/scan', { method: 'POST' });
}

async function triggerProcess() {
    return api('/api/process', { method: 'POST' });
}

// --- レンダリング ---
function renderStats() {
    const c = state.counts;
    dom.statTotal.textContent = c.total || 0;
    dom.statDone.textContent = c.done || 0;

    const processing =
        (c.downloading || 0) + (c.transcribing || 0) +
        (c.summarizing || 0) + (c.pending || 0);
    dom.statProcessing.textContent = processing;
}

function renderStatusIndicator() {
    // statusIndicatorのクラスをリセット
    dom.statusIndicator.classList.remove('processing', 'active', 'inactive');

    if (state.isProcessing) {
        dom.statusIndicator.classList.add('processing');
        dom.statusIndicator.title = '処理中';
        dom.statusText.textContent = '処理中';
    } else if (state.counts && state.isMonitoring !== undefined) {
        // 新しいAPIレスポンスの形
        if (state.isMonitoring) {
            dom.statusIndicator.classList.add('active');
            dom.statusIndicator.title = '監視中';
            dom.statusText.textContent = '監視中';
        } else {
            dom.statusIndicator.classList.add('inactive');
            dom.statusIndicator.title = '待機中';
            dom.statusText.textContent = '待機中';
        }
    } else {
        // 古いAPIのフォールバック
        dom.statusIndicator.classList.add('inactive');
        dom.statusIndicator.title = '待機中';
        dom.statusText.textContent = '待機中';
    }
}

const STATUS_LABELS = {
    done: '完了',
    pending: '待機中',
    downloading: 'ダウンロード中',
    transcribing: '文字起こし中',
    summarizing: '要約中',
    error: 'エラー',
};

function formatDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    const now = new Date();
    const diff = now - d;

    if (diff < 60_000) return 'たった今';
    if (diff < 3600_000) return `${Math.floor(diff / 60_000)}分前`;
    if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}時間前`;
    if (diff < 172800_000) return '昨日';

    return `${d.getMonth() + 1}/${d.getDate()}`;
}

function formatDuration(seconds) {
    if (!seconds) return '';
    const m = Math.floor(seconds / 60);
    if (m < 60) return `${m}分`;
    const h = Math.floor(m / 60);
    const rm = m % 60;
    return `${h}時間${rm > 0 ? rm + '分' : ''}`;
}

function renderEpisodes() {
    dom.loading.classList.add('hidden');

    if (state.episodes.length === 0) {
        dom.emptyState.classList.remove('hidden');
        dom.episodesList.innerHTML = '';
        return;
    }

    dom.emptyState.classList.add('hidden');
    dom.episodesList.innerHTML = state.episodes.map(ep => `
        <article class="episode-card status-${ep.status}" data-id="${ep.id}">
            <div class="episode-podcast">${escapeHtml(ep.podcast_title)}</div>
            <div class="episode-title">${escapeHtml(ep.episode_title)}</div>
            <div class="episode-meta">
                <span class="episode-date">${formatDate(ep.played_at)}${ep.duration ? ' · ' + formatDuration(ep.duration) : ''}</span>
                <span class="episode-badge badge-${ep.status}">${STATUS_LABELS[ep.status] || ep.status}</span>
            </div>
        </article>
    `).join('');

    // カードクリックイベント
    dom.episodesList.querySelectorAll('.episode-card').forEach(card => {
        card.addEventListener('click', () => {
            const id = parseInt(card.dataset.id);
            openEpisodeDetail(id);
        });
    });
}

// --- モーダル ---
async function openEpisodeDetail(id) {
    const ep = state.episodes.find(e => e.id === id);
    if (!ep) return;

    dom.modalPodcast.textContent = ep.podcast_title;
    dom.modalDate.textContent = formatDate(ep.played_at);
    dom.modalTitle.textContent = ep.episode_title;

    // ステータスバッジ
    dom.modalStatus.textContent = STATUS_LABELS[ep.status] || ep.status;
    dom.modalStatus.className = `modal-status-badge badge-${ep.status}`;

    // 要約
    if (ep.summary) {
        // HTMLかMarkdownかを判定（<!DOCTYPE や <html で始まるならHTML）
        const isHtml = /^\s*<!DOCTYPE|^\s*<html/i.test(ep.summary);
        if (isHtml) {
            // HTML要約: sandboxed iframe で表示
            const iframe = document.createElement('iframe');
            iframe.sandbox = 'allow-same-origin';
            iframe.style.cssText = 'width:100%;border:none;border-radius:12px;background:#0f0f2a;min-height:300px;';
            iframe.srcdoc = ep.summary;
            dom.modalSummary.innerHTML = '';
            dom.modalSummary.appendChild(iframe);

            // iframe内のコンテンツの高さに合わせて自動リサイズ
            iframe.onload = () => {
                try {
                    const doc = iframe.contentDocument || iframe.contentWindow.document;
                    const height = doc.documentElement.scrollHeight;
                    iframe.style.height = height + 'px';
                } catch (e) {
                    iframe.style.height = '600px'; // フォールバック
                }
            };
        } else {
            // 旧Markdown要約: 従来の簡易レンダラーで表示（後方互換）
            dom.modalSummary.innerHTML = renderMarkdown(ep.summary);
        }
    } else if (ep.status === 'done') {
        dom.modalSummary.innerHTML = '<div class="no-content"><span class="no-icon">📝</span><p>要約がありません</p></div>';
    } else {
        const msgs = {
            pending: '処理待ちです...',
            downloading: '音声をダウンロード中...',
            transcribing: '文字起こし中... しばらくお待ちください',
            summarizing: '要約を生成中...',
            error: '処理中にエラーが発生しました',
        };
        dom.modalSummary.innerHTML = `<div class="no-content"><span class="no-icon">${ep.status === 'error' ? '⚠️' : '⏳'}</span><p>${msgs[ep.status] || '処理中...'}</p></div>`;
    }

    // 文字起こし
    if (ep.transcript) {
        dom.modalTranscript.textContent = ep.transcript;
    } else {
        dom.modalTranscript.innerHTML = '<div class="no-content"><span class="no-icon">🎤</span><p>文字起こしデータがありません</p></div>';
    }

    // タブをリセット
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
    document.querySelector('.tab-btn[data-tab="summary"]').classList.add('active');
    document.getElementById('tab-summary').classList.add('active');

    // モーダルを開く
    dom.modalOverlay.classList.remove('hidden');
    requestAnimationFrame(() => {
        dom.modalOverlay.classList.add('visible');
    });
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    dom.modalOverlay.classList.remove('visible');
    setTimeout(() => {
        dom.modalOverlay.classList.add('hidden');
        document.body.style.overflow = '';
    }, 350);
}

// --- 簡易Markdownレンダラー ---
function renderMarkdown(text) {
    let html = escapeHtml(text);

    // Headers
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Unordered lists
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');

    // Blockquotes
    html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');

    // Paragraphs - 空行で区切る
    html = html.replace(/\n\n/g, '</p><p>');
    html = `<p>${html}</p>`;

    // 余計なタグをクリーン
    html = html.replace(/<p>\s*<(h[1-3]|ul|blockquote)/g, '<$1');
    html = html.replace(/<\/(h[1-3]|ul|blockquote)>\s*<\/p>/g, '</$1>');
    html = html.replace(/<p>\s*<\/p>/g, '');

    return html;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// --- ステータスバー ---
function showStatus(message) {
    dom.statusText.textContent = message;
    dom.statusBar.classList.remove('hidden');
    setTimeout(() => {
        dom.statusBar.classList.add('hidden');
    }, 4000);
}

// --- イベントリスナー ---
dom.btnScan.addEventListener('click', async () => {
    dom.btnScan.classList.add('spinning');
    try {
        const result = await triggerScan();
        showStatus(`${result.new_episodes} 件の新しいエピソードを検出`);
        if (result.new_episodes > 0) {
            await triggerProcess();
        }
        await refresh();
    } catch (e) {
        showStatus('スキャンに失敗しました');
        console.error(e);
    } finally {
        dom.btnScan.classList.remove('spinning');
    }
});

// 監視モードイベント
dom.btnMonitor.addEventListener('click', async () => {
    dom.btnMonitor.classList.add('spinning'); // 一時的なフィードバック
    try {
        const result = await api('/api/monitor', { method: 'POST' });
        showStatus(result.message);
        await refresh();
    } catch (e) {
        showStatus('監視モードの起動に失敗しました');
        console.error(e);
    } finally {
        setTimeout(() => dom.btnMonitor.classList.remove('spinning'), 1000);
    }
});

dom.modalClose.addEventListener('click', closeModal);

// タブ切り替え
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`tab-${tab}`).classList.add('active');
    });
});

// スワイプで戻る（モーダル）
let touchStartX = 0;
dom.modalOverlay.addEventListener('touchstart', e => {
    touchStartX = e.touches[0].clientX;
}, { passive: true });
dom.modalOverlay.addEventListener('touchend', e => {
    const diff = e.changedTouches[0].clientX - touchStartX;
    if (diff > 80) closeModal(); // 右スワイプで閉じる
}, { passive: true });

// --- 更新ループ ---
async function refresh() {
    try {
        await fetchEpisodes();
        await fetchStatus();
        renderStats();
        renderStatusIndicator();
        renderEpisodes();
    } catch (e) {
        console.error('更新エラー:', e);
    }
}

// 初期ロード
refresh();

// 定期更新
setInterval(refresh, POLL_INTERVAL);

// Page Visibility API: ページが表示されたら即座に更新
document.addEventListener('visibilitychange', () => {
    if (!document.hidden) refresh();
});

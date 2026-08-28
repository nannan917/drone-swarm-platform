/**
 * 主应用模块
 * 负责初始化、WebSocket连接、全局事件处理
 */
const App = (function() {
    let ws = null;
    let wsReconnectTimer = null;
    let currentTab = 'drones';

    function init() {
        console.log('[App] 无人机集群管理平台启动');

        // 初始化地图
        if (window.MapModule) {
            MapModule.init();
        }

        // 加载数据
        loadAllData();

        // 连接WebSocket
        connectWebSocket();

        // 定时刷新统计
        setInterval(refreshStats, 5000);

        console.log('[App] 初始化完成');
    }

    function loadAllData() {
        if (window.DronePanel) DronePanel.loadDrones();
        if (window.MissionPanel) {
            MissionPanel.loadMissions();
            MissionPanel.loadSwarmGroups();
        }
        loadLogs();
    }

    async function refreshStats() {
        try {
            const res = await fetch('/api/v1/system/stats');
            const stats = await res.json();
            document.getElementById('stat-total-val').textContent = stats.total_drones;
            document.getElementById('stat-online-val').textContent = stats.online_drones;
            document.getElementById('stat-flying-val').textContent = stats.flying_drones;
            document.getElementById('stat-offline-val').textContent = stats.offline_drones;
            document.getElementById('stat-battery-val').textContent = stats.avg_battery + '%';
        } catch (e) {
            // 静默失败
        }
    }

    /**
     * WebSocket连接
     */
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;

        try {
            ws = new WebSocket(wsUrl);
        } catch (e) {
            console.error('[WS] 创建连接失败:', e);
            scheduleReconnect();
            return;
        }

        ws.onopen = function() {
            console.log('[WS] 已连接到遥测服务');
            updateWsStatus('connected', '已连接');
            if (wsReconnectTimer) {
                clearTimeout(wsReconnectTimer);
                wsReconnectTimer = null;
            }
        };

        ws.onmessage = function(event) {
            try {
                const msg = JSON.parse(event.data);
                handleWsMessage(msg);
            } catch (e) {
                console.error('[WS] 消息解析失败:', e);
            }
        };

        ws.onclose = function() {
            console.log('[WS] 连接已关闭');
            updateWsStatus('error', '已断开');
            scheduleReconnect();
        };

        ws.onerror = function(e) {
            console.error('[WS] 连接错误:', e);
            updateWsStatus('error', '连接错误');
        };
    }

    function scheduleReconnect() {
        if (wsReconnectTimer) return;
        console.log('[WS] 5秒后重连...');
        updateWsStatus('', '重连中');
        wsReconnectTimer = setTimeout(() => {
            wsReconnectTimer = null;
            connectWebSocket();
        }, 5000);
    }

    function updateWsStatus(cls, text) {
        const el = document.getElementById('ws-status');
        el.className = 'ws-status ' + cls;
        el.querySelector('.ws-text').textContent = text;
    }

    /**
     * 处理WebSocket消息
     */
    function handleWsMessage(msg) {
        switch (msg.type) {
            case 'telemetry':
                handleTelemetry(msg.data);
                break;
            case 'drone_registered':
                console.log('[WS] 无人机注册:', msg.drone_id);
                if (window.DronePanel) DronePanel.loadDrones();
                addLog('INFO', 'system', null, `无人机注册: ${msg.drone_id}`);
                break;
            case 'drone_removed':
                console.log('[WS] 无人机移除:', msg.drone_id);
                if (window.DronePanel) DronePanel.removeDrone(msg.drone_id);
                if (window.MapModule) MapModule.removeDroneMarker(msg.drone_id);
                addLog('WARNING', 'system', null, `无人机移除: ${msg.drone_id}`);
                break;
            case 'mission_created':
            case 'mission_started':
            case 'mission_cancelled':
                if (window.MissionPanel) MissionPanel.loadMissions();
                addLog('INFO', 'mission', null, `任务事件: ${msg.type} - ${msg.mission_id}`);
                break;
            case 'swarm_command':
                addLog('INFO', 'swarm', null, `编队指令: ${msg.command} -> ${msg.group_id}`);
                break;
            case 'event':
                addLog(msg.data.level, msg.data.source, msg.data.drone_id, msg.data.message);
                break;
            case 'connected':
                console.log('[WS] 服务端确认连接');
                break;
            default:
                console.log('[WS] 未知消息类型:', msg.type);
        }
    }

    function handleTelemetry(data) {
        // 更新地图标记
        if (window.MapModule) {
            MapModule.updateDroneMarker(data);
        }
        // 更新无人机面板
        if (window.DronePanel) {
            DronePanel.updateTelemetry(data);
        }
    }

    /**
     * 标签切换
     */
    function switchTab(tab) {
        currentTab = tab;
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === 'tab-' + tab);
        });

        // 切换到对应标签时刷新数据
        if (tab === 'missions' && window.MissionPanel) MissionPanel.loadMissions();
        if (tab === 'swarm' && window.MissionPanel) MissionPanel.loadSwarmGroups();
        if (tab === 'logs') loadLogs();
    }

    /**
     * 日志管理
     */
    let logEntries = [];

    function addLog(level, source, drone_id, message) {
        const entry = {
            time: new Date().toLocaleTimeString(),
            level, source, drone_id, message,
        };
        logEntries.unshift(entry);
        if (logEntries.length > 500) logEntries.pop();
        renderLogs();
    }

    function renderLogs() {
        const container = document.getElementById('log-list');
        if (!container) return;
        container.innerHTML = logEntries.map(e => `
            <div class="log-entry ${e.level}">
                <span class="log-time">${e.time}</span>
                <span class="log-level">${e.level}</span>
                <span class="log-source">[${e.source}${e.drone_id ? '/' + e.drone_id : ''}]</span>
                ${e.message}
            </div>
        `).join('');
    }

    async function loadLogs() {
        try {
            const res = await fetch('/api/v1/system/events?limit=100');
            const logs = await res.json();
            logEntries = logs.map(l => ({
                time: new Date(l.timestamp).toLocaleTimeString(),
                level: l.level,
                source: l.source,
                drone_id: l.drone_id,
                message: l.message,
            }));
            renderLogs();
        } catch (e) {
            console.error('[App] 加载日志失败:', e);
        }
    }

    function clearLogs() {
        logEntries = [];
        renderLogs();
    }

    /**
     * 弹窗管理
     */
    function openAddDroneModal() {
        document.getElementById('add-drone-modal').classList.add('active');
    }

    function openMissionModal() {
        // 填充无人机下拉
        const select = document.getElementById('mission-drone');
        const drones = window.DronePanel ? DronePanel.getAllDrones() : {};
        select.innerHTML = '<option value="">暂不分配</option>' +
            Object.values(drones).map(d => `<option value="${d.drone_id}">${d.name} (${d.drone_id})</option>`).join('');
        document.getElementById('mission-modal').classList.add('active');
    }

    function openSwarmModal() {
        document.getElementById('swarm-modal').classList.add('active');
    }

    function closeModal(id) {
        document.getElementById(id).classList.remove('active');
    }

    /**
     * 提交添加无人机
     */
    async function submitAddDrone() {
        const data = {
            drone_id: document.getElementById('form-drone-id').value.trim(),
            name: document.getElementById('form-drone-name').value.trim(),
            model: document.getElementById('form-drone-model').value,
            firmware: document.getElementById('form-drone-firmware').value,
            connection_type: document.getElementById('form-conn-type').value,
            connection_address: document.getElementById('form-conn-addr').value,
            group_id: document.getElementById('form-group-id').value.trim() || null,
        };

        if (!data.drone_id || !data.name) {
            showToast('请填写无人机ID和名称', 'warning');
            return;
        }

        try {
            const res = await fetch('/api/v1/drones', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            if (res.ok) {
                const drone = await res.json();
                showToast(`无人机 ${drone.name} 注册成功`, 'success');
                closeModal('add-drone-modal');
                if (window.DronePanel) DronePanel.loadDrones();
            } else {
                const err = await res.json();
                showToast(err.message || '注册失败', 'error');
            }
        } catch (e) {
            showToast('注册失败: ' + e.message, 'error');
        }
    }

    /**
     * 提交创建任务
     */
    async function submitMission() {
        let waypoints = [];
        try {
            waypoints = JSON.parse(document.getElementById('mission-waypoints').value);
        } catch {
            showToast('航点JSON格式错误', 'error');
            return;
        }

        const data = {
            name: document.getElementById('mission-name').value.trim(),
            description: document.getElementById('mission-desc').value,
            drone_id: document.getElementById('mission-drone').value || null,
            waypoints: waypoints,
            max_altitude: parseFloat(document.getElementById('mission-max-alt').value) || 120,
            max_speed: parseFloat(document.getElementById('mission-max-speed').value) || 15,
        };

        if (!data.name) {
            showToast('请填写任务名称', 'warning');
            return;
        }

        try {
            const res = await fetch('/api/v1/missions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            if (res.ok) {
                showToast('任务创建成功', 'success');
                closeModal('mission-modal');
                if (window.MissionPanel) MissionPanel.loadMissions();
            } else {
                const err = await res.json();
                showToast(err.message || '创建失败', 'error');
            }
        } catch (e) {
            showToast('创建失败: ' + e.message, 'error');
        }
    }

    /**
     * 提交创建编队
     */
    async function submitSwarm() {
        const data = {
            group_id: document.getElementById('swarm-id').value.trim(),
            name: document.getElementById('swarm-name').value.trim(),
            formation_type: document.getElementById('swarm-formation').value,
            description: document.getElementById('swarm-desc').value,
        };

        if (!data.group_id || !data.name) {
            showToast('请填写编队ID和名称', 'warning');
            return;
        }

        try {
            const res = await fetch('/api/v1/swarm/groups', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            if (res.ok) {
                showToast('编队创建成功', 'success');
                closeModal('swarm-modal');
                if (window.MissionPanel) MissionPanel.loadSwarmGroups();
            } else {
                const err = await res.json();
                showToast(err.message || '创建失败', 'error');
            }
        } catch (e) {
            showToast('创建失败: ' + e.message, 'error');
        }
    }

    function closeDetailPanel() {
        document.getElementById('right-panel').classList.add('collapsed');
    }

    /**
     * Toast提示
     */
    function showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('fade-out');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // 暴露全局函数供HTML调用
    return {
        init,
        switchTab,
        openAddDroneModal,
        openMissionModal,
        openSwarmModal,
        closeModal,
        submitAddDrone,
        submitMission,
        submitSwarm,
        closeDetailPanel,
        showToast,
        clearLogs,
    };
})();

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    App.init();
});

// 全局函数别名（供HTML onclick调用）
window.switchTab = App.switchTab;
window.openAddDroneModal = App.openAddDroneModal;
window.openMissionModal = App.openMissionModal;
window.openSwarmModal = App.openSwarmModal;
window.closeModal = App.closeModal;
window.submitAddDrone = App.submitAddDrone;
window.submitMission = App.submitMission;
window.submitSwarm = App.submitSwarm;
window.closeDetailPanel = App.closeDetailPanel;
window.clearLogs = App.clearLogs;
window.centerMap = function() { if (window.MapModule) MapModule.centerMap(); };
window.toggleTrails = function() { if (window.MapModule) MapModule.toggleTrails(); };

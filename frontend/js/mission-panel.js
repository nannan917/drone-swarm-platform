/**
 * 任务与编队面板模块
 */
const MissionPanel = (function() {
    let missions = [];
    let swarmGroups = [];

    async function loadMissions() {
        try {
            const res = await fetch('/api/v1/missions');
            missions = await res.json();
            renderMissions();
        } catch (e) {
            console.error('[MissionPanel] 加载任务失败:', e);
        }
    }

    async function loadSwarmGroups() {
        try {
            const res = await fetch('/api/v1/swarm/groups');
            swarmGroups = await res.json();
            renderSwarm();
        } catch (e) {
            console.error('[MissionPanel] 加载编队失败:', e);
        }
    }

    function renderMissions() {
        const container = document.getElementById('mission-list');
        if (missions.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>暂无任务</p></div>';
            return;
        }
        container.innerHTML = missions.map(m => {
            const waypoints = safeParseJSON(m.waypoints, []);
            return `
                <div class="mission-card">
                    <div class="mission-card-header">
                        <span class="mission-card-name">${m.name}</span>
                        <span class="mission-card-status mission-status-${m.status}">${m.status}</span>
                    </div>
                    <div class="mission-card-meta">
                        <span>${m.mission_id}</span>
                        <span>${waypoints.length} 航点</span>
                    </div>
                    <div class="mission-progress">
                        <div class="mission-progress-fill" style="width: ${m.progress_percent || 0}%"></div>
                    </div>
                    <div class="mission-card-meta" style="margin-bottom: 0;">
                        <span>进度: ${(m.progress_percent || 0).toFixed(0)}%</span>
                        <span>${m.current_waypoint || 0}/${m.total_waypoints || 0}</span>
                    </div>
                    <div class="mission-card-actions" style="margin-top: 8px;">
                        ${m.status === 'pending' ? `<button class="btn btn-small btn-success" onclick="MissionPanel.startMission('${m.mission_id}')">开始</button>` : ''}
                        ${m.status === 'running' ? `<button class="btn btn-small btn-warning" onclick="MissionPanel.pauseMission('${m.mission_id}')">暂停</button>` : ''}
                        ${m.status === 'running' || m.status === 'paused' ? `<button class="btn btn-small btn-danger" onclick="MissionPanel.cancelMission('${m.mission_id}')">取消</button>` : ''}
                        <button class="btn btn-small" onclick="MissionPanel.viewWaypoints('${m.mission_id}')">航点</button>
                    </div>
                </div>
            `;
        }).join('');
    }

    function renderSwarm() {
        const container = document.getElementById('swarm-list');
        if (swarmGroups.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>暂无编队组</p></div>';
            return;
        }
        container.innerHTML = swarmGroups.map(g => `
            <div class="swarm-card">
                <div class="swarm-card-header">
                    <span class="swarm-card-name">${g.name}</span>
                    <span class="swarm-card-formation">${g.formation_type}</span>
                </div>
                <div class="swarm-card-members">
                    ${g.group_id} · ${g.member_count}架 · 长机: ${g.leader_drone_id || '未设置'}
                </div>
                <div class="swarm-card-actions">
                    <button class="btn btn-small btn-primary" onclick="MissionPanel.swarmCommand('${g.group_id}', 'takeoff_all')">批量起飞</button>
                    <button class="btn btn-small" onclick="MissionPanel.swarmCommand('${g.group_id}', 'land_all')">批量降落</button>
                    <button class="btn btn-small btn-danger" onclick="MissionPanel.swarmCommand('${g.group_id}', 'rtl_all')">批量返航</button>
                </div>
            </div>
        `).join('');
    }

    async function startMission(mission_id) {
        try {
            const res = await fetch(`/api/v1/missions/${mission_id}/start`, { method: 'POST' });
            const result = await res.json();
            App.showToast(result.message || '任务已开始', result.success ? 'success' : 'error');
            loadMissions();
        } catch (e) {
            App.showToast('操作失败: ' + e.message, 'error');
        }
    }

    async function pauseMission(mission_id) {
        try {
            const res = await fetch(`/api/v1/missions/${mission_id}/pause`, { method: 'POST' });
            const result = await res.json();
            App.showToast(result.message || '任务已暂停', result.success ? 'success' : 'error');
            loadMissions();
        } catch (e) {
            App.showToast('操作失败: ' + e.message, 'error');
        }
    }

    async function cancelMission(mission_id) {
        if (!confirm('确定取消该任务？无人机将自动返航。')) return;
        try {
            const res = await fetch(`/api/v1/missions/${mission_id}/cancel`, { method: 'POST' });
            const result = await res.json();
            App.showToast(result.message || '任务已取消', result.success ? 'success' : 'error');
            loadMissions();
        } catch (e) {
            App.showToast('操作失败: ' + e.message, 'error');
        }
    }

    async function viewWaypoints(mission_id) {
        try {
            const res = await fetch(`/api/v1/missions/${mission_id}/waypoints`);
            const data = await res.json();
            alert(`航点列表 (${data.count}个):\n\n` +
                data.waypoints.map((w, i) =>
                    `${i + 1}. 纬度:${w.lat}, 经度:${w.lon}, 高度:${w.alt}m, 速度:${w.speed}m/s`
                ).join('\n')
            );
        } catch (e) {
            App.showToast('获取航点失败', 'error');
        }
    }

    async function swarmCommand(group_id, command) {
        try {
            const res = await fetch(`/api/v1/swarm/groups/${group_id}/command`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command, params: {} }),
            });
            const result = await res.json();
            App.showToast(`编队指令已发送，影响 ${result.affected || 0} 架无人机`, 'success');
        } catch (e) {
            App.showToast('编队指令失败: ' + e.message, 'error');
        }
    }

    function safeParseJSON(str, fallback) {
        try { return JSON.parse(str); } catch { return fallback; }
    }

    return {
        loadMissions,
        loadSwarmGroups,
        startMission,
        pauseMission,
        cancelMission,
        viewWaypoints,
        swarmCommand,
    };
})();

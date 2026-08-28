/**
 * 无人机面板模块
 * 负责无人机列表渲染、详情面板、控制指令
 */
const DronePanel = (function() {
    let drones = {};        // drone_id -> drone data
    let selectedDrone = null;
    let searchFilter = '';

    /**
     * 加载无人机列表
     */
    async function loadDrones() {
        try {
            const res = await fetch('/api/v1/drones');
            const data = await res.json();
            drones = {};
            data.forEach(d => { drones[d.drone_id] = d; });
            renderDroneList();
            updateStats();
        } catch (e) {
            console.error('[DronePanel] 加载无人机列表失败:', e);
        }
    }

    /**
     * 渲染无人机列表
     */
    function renderDroneList() {
        const container = document.getElementById('drone-list');
        const filtered = Object.values(drones).filter(d => {
            if (!searchFilter) return true;
            const q = searchFilter.toLowerCase();
            return d.name.toLowerCase().includes(q) ||
                   d.drone_id.toLowerCase().includes(q) ||
                   (d.group_id || '').toLowerCase().includes(q);
        });

        if (filtered.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>${searchFilter ? '无匹配无人机' : '暂无无人机'}</p>
                    <p class="empty-hint">点击右上角"添加无人机"注册</p>
                </div>
            `;
            return;
        }

        container.innerHTML = filtered.map(d => {
            const batteryClass = d.battery_percent < 30 ? 'low' : d.battery_percent < 60 ? 'medium' : '';
            const selected = selectedDrone === d.drone_id ? 'selected' : '';
            return `
                <div class="drone-card status-${d.status} ${selected}"
                     onclick="DronePanel.selectDrone('${d.drone_id}')"
                     data-drone-id="${d.drone_id}">
                    <div class="drone-card-header">
                        <div>
                            <div class="drone-card-name">${d.name} ${d.is_leader ? '👑' : ''}</div>
                            <div class="drone-card-id">${d.drone_id} · SYS ${d.sys_id || '-'}</div>
                        </div>
                        <span class="drone-card-status">${d.status}</span>
                    </div>
                    <div class="drone-card-stats">
                        <div class="drone-card-stat">
                            <span class="drone-card-stat-label">高度</span>
                            <span class="drone-card-stat-value">${(d.relative_altitude || 0).toFixed(0)}m</span>
                        </div>
                        <div class="drone-card-stat">
                            <span class="drone-card-stat-label">速度</span>
                            <span class="drone-card-stat-value">${(d.ground_speed || 0).toFixed(1)}</span>
                        </div>
                        <div class="drone-card-stat">
                            <span class="drone-card-stat-label">电量</span>
                            <span class="drone-card-stat-value">${(d.battery_percent || 0).toFixed(0)}%</span>
                        </div>
                    </div>
                    <div class="battery-bar">
                        <div class="battery-fill ${batteryClass}" style="width: ${d.battery_percent || 0}%"></div>
                    </div>
                </div>
            `;
        }).join('');
    }

    /**
     * 选择无人机，显示详情
     */
    function selectDrone(drone_id) {
        selectedDrone = drone_id;
        renderDroneList();
        renderDetailPanel();
        if (window.MapModule) {
            MapModule.centerOnDrone(drone_id);
        }
    }

    /**
     * 渲染详情面板
     */
    function renderDetailPanel() {
        const body = document.getElementById('detail-body');
        const title = document.getElementById('detail-title');

        if (!selectedDrone || !drones[selectedDrone]) {
            title.textContent = '无人机详情';
            body.innerHTML = '<div class="empty-state"><p>选择一架无人机查看详情</p></div>';
            return;
        }

        const d = drones[selectedDrone];
        title.textContent = d.name;

        body.innerHTML = `
            <!-- 基本信息 -->
            <div class="detail-section">
                <div class="detail-section-title">基本信息</div>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-item-label">无人机ID</div>
                        <div class="detail-item-value small">${d.drone_id}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-item-label">系统ID</div>
                        <div class="detail-item-value small">${d.sys_id || '-'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-item-label">型号</div>
                        <div class="detail-item-value small">${d.model}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-item-label">固件</div>
                        <div class="detail-item-value small">${d.firmware}</div>
                    </div>
                    <div class="detail-item full">
                        <div class="detail-item-label">连接地址</div>
                        <div class="detail-item-value small">${d.connection_type}://${d.connection_address}</div>
                    </div>
                </div>
            </div>

            <!-- 实时状态 -->
            <div class="detail-section">
                <div class="detail-section-title">实时状态</div>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-item-label">连接模式</div>
                        <div class="detail-item-value" style="color: ${d.mode === 'real' ? '#10b981' : '#f59e0b'}; font-size: 14px;">
                            ${d.mode === 'real' ? '真实连接' : '模拟模式'}
                        </div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-item-label">飞行状态</div>
                        <div class="detail-item-value" style="color: ${getStatusColor(d.status)}">${d.status}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-item-label">飞行模式</div>
                        <div class="detail-item-value small">${d.flight_mode || '-'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-item-label">解锁状态</div>
                        <div class="detail-item-value" style="color: ${d.armed ? '#10b981' : '#6b7280'}">
                            ${d.armed ? '已解锁' : '已上锁'}
                        </div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-item-label">航向</div>
                        <div class="detail-item-value">${(d.heading || 0).toFixed(0)}°</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-item-label">相对高度</div>
                        <div class="detail-item-value">${(d.relative_altitude || 0).toFixed(1)}m</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-item-label">纬度</div>
                        <div class="detail-item-value small">${(d.latitude || 0).toFixed(6)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-item-label">经度</div>
                        <div class="detail-item-value small">${(d.longitude || 0).toFixed(6)}</div>
                    </div>
                </div>
            </div>

            <!-- 姿态 -->
            <div class="detail-section">
                <div class="detail-section-title">飞行姿态</div>
                <div class="attitude-display">
                    <div class="attitude-gauge">
                        <div class="attitude-gauge-label">横滚 ROLL</div>
                        <div class="attitude-gauge-value">${(d.roll || 0).toFixed(1)}°</div>
                    </div>
                    <div class="attitude-gauge">
                        <div class="attitude-gauge-label">俯仰 PITCH</div>
                        <div class="attitude-gauge-value">${(d.pitch || 0).toFixed(1)}°</div>
                    </div>
                    <div class="attitude-gauge">
                        <div class="attitude-gauge-label">偏航 YAW</div>
                        <div class="attitude-gauge-value">${(d.yaw || 0).toFixed(1)}°</div>
                    </div>
                </div>
            </div>

            <!-- 电池与GPS -->
            <div class="detail-section">
                <div class="detail-section-title">能源与导航</div>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-item-label">电池电量</div>
                        <div class="detail-item-value" style="color: ${d.battery_percent < 30 ? '#ef4444' : d.battery_percent < 60 ? '#f59e0b' : '#10b981'}">${(d.battery_percent || 0).toFixed(1)}%</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-item-label">电池电压</div>
                        <div class="detail-item-value">${(d.battery_voltage || 0).toFixed(2)}V</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-item-label">地速</div>
                        <div class="detail-item-value">${(d.ground_speed || 0).toFixed(2)}m/s</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-item-label">垂速</div>
                        <div class="detail-item-value">${(d.vertical_speed || 0).toFixed(2)}m/s</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-item-label">GPS卫星</div>
                        <div class="detail-item-value">${d.gps_satellites || 0}颗</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-item-label">相对高度</div>
                        <div class="detail-item-value">${(d.relative_altitude || 0).toFixed(1)}m</div>
                    </div>
                </div>
            </div>

            <!-- 飞行控制 -->
            <div class="detail-section">
                <div class="detail-section-title">飞行控制</div>
                <div class="control-group">
                    <button class="control-btn arm" onclick="DronePanel.sendCommand('arm')">解锁 ARM</button>
                    <button class="control-btn disarm" onclick="DronePanel.sendCommand('disarm')">上锁 DISARM</button>
                    <button class="control-btn takeoff" onclick="DronePanel.takeoff()">起飞 TAKEOFF</button>
                    <button class="control-btn land" onclick="DronePanel.sendCommand('land')">降落 LAND</button>
                    <button class="control-btn rtl" onclick="DronePanel.sendCommand('rtl')">返航 RTL</button>
                    <button class="control-btn" onclick="DronePanel.goTo()">飞往 GOTO</button>
                </div>
            </div>

            <!-- 最后心跳 -->
            <div class="detail-section">
                <div class="detail-section-title">连接信息</div>
                <div class="detail-grid">
                    <div class="detail-item full">
                        <div class="detail-item-label">最后心跳</div>
                        <div class="detail-item-value small">${d.last_heartbeat ? new Date(d.last_heartbeat).toLocaleString() : '从未连接'}</div>
                    </div>
                    <div class="detail-item full">
                        <div class="detail-item-label">注册时间</div>
                        <div class="detail-item-value small">${d.registered_at ? new Date(d.registered_at).toLocaleString() : '-'}</div>
                    </div>
                </div>
            </div>
        `;
    }

    function getStatusColor(status) {
        const map = {
            'flying': '#00d4ff', 'takeoff': '#00d4ff', 'landing': '#00d4ff',
            'standby': '#f59e0b', 'armed': '#10b981',
            'offline': '#6b7280', 'error': '#ef4444', 'emergency': '#ef4444',
        };
        return map[status] || '#8b9bb4';
    }

    /**
     * 发送控制指令
     */
    async function sendCommand(command, params = {}) {
        if (!selectedDrone) return;
        try {
            const res = await fetch(`/api/v1/drones/${selectedDrone}/command`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command, params }),
            });
            const result = await res.json();
            if (result.success) {
                App.showToast(`指令已发送: ${command}`, 'success');
            } else {
                App.showToast(result.message || '指令发送失败', 'error');
            }
        } catch (e) {
            App.showToast('指令发送失败: ' + e.message, 'error');
        }
    }

    function takeoff() {
        const alt = prompt('请输入起飞高度（米）:', '30');
        if (alt !== null) {
            sendCommand('takeoff', { altitude: parseFloat(alt) || 30 });
        }
    }

    function goTo() {
        const lat = prompt('请输入目标纬度:', '22.5431');
        if (lat === null) return;
        const lon = prompt('请输入目标经度:', '113.9440');
        if (lon === null) return;
        const alt = prompt('请输入目标高度（米）:', '50');
        sendCommand('go_to', {
            latitude: parseFloat(lat),
            longitude: parseFloat(lon),
            altitude: parseFloat(alt) || 50,
        });
    }

    /**
     * 更新遥测数据（由WebSocket调用）
     */
    function updateTelemetry(telemetry) {
        const did = telemetry.drone_id;
        if (!drones[did]) {
            // 新无人机，添加到列表
            drones[did] = {
                drone_id: did,
                name: did,
                status: telemetry.status,
                ...telemetry,
            };
        } else {
            Object.assign(drones[did], telemetry);
        }

        // 更新列表（节流，每1秒更新一次DOM）
        if (!this._lastRender || Date.now() - this._lastRender > 1000) {
            renderDroneList();
            this._lastRender = Date.now();
        }

        // 如果是当前选中的无人机，更新详情
        if (selectedDrone === did) {
            renderDetailPanel();
        }
    }

    function removeDrone(drone_id) {
        delete drones[drone_id];
        if (selectedDrone === drone_id) {
            selectedDrone = null;
            renderDetailPanel();
        }
        renderDroneList();
        updateStats();
    }

    function filterDrones(query) {
        searchFilter = query;
        renderDroneList();
    }

    function updateStats() {
        const list = Object.values(drones);
        document.getElementById('stat-total-val').textContent = list.length;
        document.getElementById('stat-online-val').textContent = list.filter(d => d.status !== 'offline').length;
        document.getElementById('stat-flying-val').textContent = list.filter(d =>
            ['flying', 'takeoff', 'landing', 'return_to_home'].includes(d.status)
        ).length;
        document.getElementById('stat-offline-val').textContent = list.filter(d => d.status === 'offline').length;
        const avgBat = list.length > 0
            ? (list.reduce((s, d) => s + (d.battery_percent || 0), 0) / list.length).toFixed(0)
            : 0;
        document.getElementById('stat-battery-val').textContent = avgBat + '%';
    }

    function getSelectedDrone() {
        return selectedDrone;
    }

    function getAllDrones() {
        return drones;
    }

    return {
        loadDrones,
        selectDrone,
        sendCommand,
        takeoff,
        goTo,
        updateTelemetry,
        removeDrone,
        filterDrones,
        updateStats,
        getSelectedDrone,
        getAllDrones,
        renderDetailPanel,
    };
})();

/**
 * 地图模块 - 基于 Leaflet
 * 负责地图初始化、无人机标记管理、轨迹绘制
 */
const MapModule = (function() {
    let map = null;
    let droneMarkers = {};  // drone_id -> marker
    let droneTrails = {};   // drone_id -> polyline
    let showTrails = true;
    const DEFAULT_CENTER = [22.5431, 113.9440]; // 深圳
    const DEFAULT_ZOOM = 14;

    function init() {
        map = L.map('map', {
            center: DEFAULT_CENTER,
            zoom: DEFAULT_ZOOM,
            zoomControl: true,
            attributionControl: false,
        });

        // 使用暗色地图瓦片
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            maxZoom: 19,
            subdomains: 'abcd',
        }).addTo(map);

        // 比例尺
        L.control.scale({ imperial: false, position: 'bottomright' }).addTo(map);

        console.log('[Map] 地图初始化完成');
    }

    /**
     * 获取无人机标记SVG图标
     */
    function getDroneIcon(status, isLeader, heading) {
        const colorMap = {
            'offline': '#6b7280',
            'standby': '#f59e0b',
            'armed': '#10b981',
            'takeoff': '#00d4ff',
            'flying': '#00d4ff',
            'landing': '#00d4ff',
            'return_to_home': '#00d4ff',
            'emergency': '#ef4444',
            'error': '#ef4444',
        };
        const color = colorMap[status] || '#6b7280';
        const glow = isLeader ? `filter: drop-shadow(0 0 6px ${color});` : '';

        const svg = `
            <div class="drone-marker-icon" style="transform: rotate(${heading || 0}deg);">
                ${status === 'flying' || status === 'takeoff' ? '<div class="drone-pulse"></div>' : ''}
                <svg class="drone-marker-svg" viewBox="0 0 24 24" fill="${color}" style="${glow}">
                    <circle cx="12" cy="12" r="3"/>
                    <path d="M12 2l2 4h-4l2-4zm0 20l2-4h-4l2 4zM2 12l4-2v4l-4-2zm20 0l-4-2v4l4-2z" opacity="0.8"/>
                    <circle cx="4" cy="8" r="2" opacity="0.6"/>
                    <circle cx="20" cy="8" r="2" opacity="0.6"/>
                    <circle cx="4" cy="16" r="2" opacity="0.6"/>
                    <circle cx="20" cy="16" r="2" opacity="0.6"/>
                </svg>
            </div>
        `;
        return L.divIcon({
            html: svg,
            className: 'drone-marker',
            iconSize: [36, 36],
            iconAnchor: [18, 18],
        });
    }

    /**
     * 更新或创建无人机标记
     */
    function updateDroneMarker(telemetry) {
        const { drone_id, latitude, longitude, status, heading, name, is_leader } = telemetry;
        const latlng = [latitude, longitude];

        if (!droneMarkers[drone_id]) {
            // 创建新标记
            const marker = L.marker(latlng, {
                icon: getDroneIcon(status, is_leader, heading),
            }).addTo(map);

            marker.bindPopup('', { maxWidth: 300 });
            marker.on('click', () => {
                if (window.DronePanel) {
                    DronePanel.selectDrone(drone_id);
                }
            });

            droneMarkers[drone_id] = marker;

            // 创建轨迹线
            if (showTrails) {
                droneTrails[drone_id] = L.polyline([latlng], {
                    color: status === 'flying' ? '#00d4ff' : '#6b7280',
                    weight: 2,
                    opacity: 0.5,
                    dashArray: '5, 5',
                }).addTo(map);
            }
        } else {
            // 更新位置
            const marker = droneMarkers[drone_id];
            marker.setLatLng(latlng);
            marker.setIcon(getDroneIcon(status, is_leader, heading));

            // 更新轨迹
            if (showTrails && droneTrails[drone_id]) {
                const path = droneTrails[drone_id].getLatLngs();
                path.push(latlng);
                if (path.length > 500) path.shift(); // 限制轨迹点数量
                droneTrails[drone_id].setLatLngs(path);
            }
        }

        // 更新弹窗内容
        updatePopup(drone_id, telemetry);
    }

    function updatePopup(drone_id, telemetry) {
        const marker = droneMarkers[drone_id];
        if (!marker) return;
        const t = telemetry;
        const html = `
            <div style="font-family: inherit; min-width: 200px;">
                <div style="font-weight: 700; font-size: 15px; margin-bottom: 8px; color: #00d4ff;">
                    ${t.name || drone_id} ${t.is_leader ? '👑' : ''}
                </div>
                <div style="font-size: 11px; color: #8b9bb4; margin-bottom: 8px;">
                    ID: ${drone_id} | SYS: ${t.sys_id || '-'}
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 12px;">
                    <div>状态: <span style="color: ${getStatusColor(t.status)}">${t.status}</span></div>
                    <div>高度: ${(t.relative_altitude || 0).toFixed(1)}m</div>
                    <div>速度: ${(t.ground_speed || 0).toFixed(1)}m/s</div>
                    <div>电量: ${(t.battery_percent || 0).toFixed(0)}%</div>
                    <div>航向: ${(t.heading || 0).toFixed(0)}°</div>
                    <div>GPS: ${t.gps_satellites || 0}颗</div>
                </div>
                <div style="margin-top: 8px; font-size: 10px; color: #5a6a82;">
                    ${t.timestamp || ''}
                </div>
            </div>
        `;
        marker.setPopupContent(html);
    }

    function getStatusColor(status) {
        const map = {
            'flying': '#00d4ff', 'takeoff': '#00d4ff', 'landing': '#00d4ff',
            'standby': '#f59e0b', 'armed': '#10b981',
            'offline': '#6b7280', 'error': '#ef4444', 'emergency': '#ef4444',
        };
        return map[status] || '#8b9bb4';
    }

    function removeDroneMarker(drone_id) {
        if (droneMarkers[drone_id]) {
            map.removeLayer(droneMarkers[drone_id]);
            delete droneMarkers[drone_id];
        }
        if (droneTrails[drone_id]) {
            map.removeLayer(droneTrails[drone_id]);
            delete droneTrails[drone_id];
        }
    }

    function centerOnDrone(drone_id) {
        if (droneMarkers[drone_id]) {
            map.setView(droneMarkers[drone_id].getLatLng(), 16, { animate: true });
        }
    }

    function centerMap() {
        const markers = Object.values(droneMarkers);
        if (markers.length > 0) {
            const group = L.featureGroup(markers);
            map.fitBounds(group.getBounds().pad(0.2));
        } else {
            map.setView(DEFAULT_CENTER, DEFAULT_ZOOM);
        }
    }

    function toggleTrails() {
        showTrails = !showTrails;
        if (showTrails) {
            Object.keys(droneMarkers).forEach(did => {
                if (!droneTrails[did] && droneMarkers[did]) {
                    droneTrails[did] = L.polyline([droneMarkers[did].getLatLng()], {
                        color: '#00d4ff', weight: 2, opacity: 0.5, dashArray: '5, 5',
                    }).addTo(map);
                }
            });
        } else {
            Object.values(droneTrails).forEach(trail => map.removeLayer(trail));
            droneTrails = {};
        }
        return showTrails;
    }

    function getMarkerCount() {
        return Object.keys(droneMarkers).length;
    }

    return {
        init,
        updateDroneMarker,
        removeDroneMarker,
        centerOnDrone,
        centerMap,
        toggleTrails,
        getMarkerCount,
    };
})();

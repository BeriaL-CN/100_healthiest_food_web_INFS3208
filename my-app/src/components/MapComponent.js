import React, { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import { useNavigate } from "react-router-dom"; 
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { getFruits } from "../data/data";

// 修复 Leaflet 默认 marker 图标在 React 打包后路径丢失的问题。
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require("leaflet/dist/images/marker-icon-2x.png"),
  iconUrl: require("leaflet/dist/images/marker-icon.png"),
  shadowUrl: require("leaflet/dist/images/marker-shadow.png"),
});

// 地图食品点使用苹果 emoji，保留原课程项目的视觉风格。
const fruitIcon = L.divIcon({
  className: 'fruit-icon', 
  html: '<div style="color: red; font-size: 20px;">🍎</div>', 
  iconSize: [30, 30], 
  iconAnchor: [15, 10],
});

// 限制地图边界，避免横向重复世界地图影响 marker 判断。
const bounds = [
  [-90, -180],
  [90, 180],
];

function MapComponent() {
  const originalWorldPosition = [0, 100]; 
  const brisbanePosition = [-27.4698, 153.0251]; 
  const [fruitMarkers, setFruitMarkers] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // source=map 会让 Django 返回已补齐/偏移后的地图坐标。
        const fruits = await getFruits({ source: "map" });
        setFruitMarkers(fruits.filter((fruit) => fruit.origin?.position));
      } catch (error) {
        console.error(error);
        setFruitMarkers([]);
      }
    };

    fetchData();
  }, []);

  // 点击 marker 后把当前食品放入路由 state，详情页可立即展示。
  const navigate = useNavigate(); 
  const handleFruitClick = (fruit) => {
    navigate("/data-details", { state: { fruit } });
  };

  return (
    <MapContainer
      center={originalWorldPosition}
      zoom={3}
      minZoom={3}
      style={{ height: "95vh", width: "100%" }}
      worldCopyJump={false}
      maxBounds={bounds}
      maxBoundsViscosity={1.0}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
      />
      {/* 渲染后端整理好的 100 个食品 marker。 */}
      {fruitMarkers &&
        fruitMarkers.map((fruit, idx) => (
          <Marker
            key={fruit.id || idx}
            position={fruit.origin.position}
            icon={fruitIcon}
          >
            <Popup>
              <strong>{fruit.displayName || fruit.name}</strong>
              <br />
              <strong>Origin region: {fruit.origin.label || "Unknown"}</strong>
              <br />
              {fruit.origin.displayOffset && (
                <>
                  <span>Marker spread for visibility</span>
                  <br />
                </>
              )}
              <strong>Source: {fruit.source}</strong>
              <br />
              <button onClick={() => handleFruitClick(fruit)}>Detail</button>
            </Popup>
          </Marker>
        ))}
      <Marker position={brisbanePosition}>
        <Popup>This is Brisbane, Australia</Popup>
      </Marker>
    </MapContainer>
  );
}

export default MapComponent;

// src/components/DataDetails.js
import React, { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { getFruits } from "../data/data";
import "./DataDetails.css";
import DataComparison from "./DataComparison";

function DataDetails() {
  // 详情页接收地图点击传来的食品，并允许再选择其他食品做对比。
  const location = useLocation();
  const navigate = useNavigate();
  const fruit = location.state?.fruit;
  const [compareFruits, setCompareFruits] = useState([]);
  const [showComparison, setShowComparison] = useState(false);

  const [fruits, setFruits] = useState([]);
  const selectedFruit = findLatestFood(fruit, fruits);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // 对比弹窗读取同一个 Django API，不直接访问外部数据源。
        const fruits = await getFruits();
        setFruits(fruits);
      } catch (error) {
        console.error(error);
        setFruits([]);
      }
    };

    fetchData();
  }, []);


  const handleAddComparison = () => {
    setShowComparison(true);
  };

  const handleSelectFruit = (selectedFruit) => {
    setCompareFruits([...compareFruits, selectedFruit]);
    setShowComparison(false);
  };

   // 处理删除对比水果的功能
   const handleRemoveComparison = (index) => {
    const updatedFruits = compareFruits.filter((_, i) => i !== index);
    setCompareFruits(updatedFruits);
  };

  return (
    <div className="data-details">
      <div className="details-toolbar">
        <button className="back-button" type="button" onClick={() => navigate("/")}>
          <span aria-hidden="true">←</span>
          Map
        </button>
        <h1>The Detail of Foods</h1>
      </div>

      <div className="fruit-comparison-container">
        {/* 当前选中的食品。 */}
        {selectedFruit ? (
          <FoodInfo food={selectedFruit} />
        ) : (
          <div className="empty-selection">
            <p>No food selected.</p>
            <button className="back-button" type="button" onClick={() => navigate("/")}>
              <span aria-hidden="true">←</span>
              Map
            </button>
          </div>
        )}

        {/* 用户额外添加的对比食品。 */}
        {compareFruits.length > 0 && (
          <div className="comparison-info">
            {compareFruits.map((f, index) => (
              <div key={f.id || index} className="fruit-info-wrapper">
                <FoodInfo food={f} />
                <button className="remove-button" onClick={() => handleRemoveComparison(index)}>
                  X
                </button>
              </div>
            ))}
          </div>
        )}

        {/* 打开对比选择列表。 */}
        <button className="add-button" onClick={handleAddComparison}>
          <span className="add-icon">+</span>
        </button>

        {/* 食品对比选择弹窗。 */}
        {showComparison && (
          <DataComparison
            fruits={fruits}
            onSelectFruit={handleSelectFruit}
            onClose={() => setShowComparison(false)}
          />
        )}
      </div>
    </div>
  );
}

function FoodInfo({ food }) {
  // Django 已把 OFF、本地 CSV、Wikidata 缓存统一成这个展示结构。
  const nutrients = food.nutrients || {};
  const metadata = food.metadata || {};
  const displayName = food.displayName || food.name;

  return (
    <div className="fruit-info">
      <h3>{displayName}</h3>
      <dl className="food-fields">
        {metadata.productName && metadata.productName !== displayName && (
          <Field label="Product" value={metadata.productName} />
        )}
        <Field label="Source" value={food.source} />
        <Field label="Category" value={food.category || "Unknown"} />
        <Field label="Origin" value={food.origin?.label || "Unknown"} />
        {metadata.originNote && <Field label="Note" value={metadata.originNote} />}
        <Field label="Calories" value={formatValue(nutrients.calories, "kcal")} />
        <Field label="Protein" value={formatValue(nutrients.protein, "g")} />
        <Field label="Fiber" value={formatValue(nutrients.fiber, "g")} />
        <Field label="Sugar" value={formatValue(nutrients.sugar, "g")} />
        <Field label="Fat" value={formatValue(nutrients.fat, "g")} />
        <Field label="Nutri-Score" value={metadata.nutriScoreGrade || "N/A"} />
        <Field label="Health Score" value={food.healthScore ?? "N/A"} />
      </dl>
    </div>
  );
}

function findLatestFood(routeFood, foods) {
  // 路由 state 可能是进入详情页时的旧对象；优先用 API 最新结果补齐 OFF 增强字段。
  if (!routeFood) {
    return null;
  }

  const routeKey = foodKey(routeFood);
  return foods.find((food) => foodKey(food) === routeKey) || routeFood;
}

function foodKey(food) {
  return (food?.displayName || food?.name || food?.id || "").toLowerCase();
}

function Field({ label, value }) {
  return (
    <div className="food-field">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function formatValue(value, unit) {
  return value === null || value === undefined ? "N/A" : `${value} ${unit}`;
}

export default DataDetails;

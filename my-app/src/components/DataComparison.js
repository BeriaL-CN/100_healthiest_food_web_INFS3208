// src/components/DataComparison.js
import React from 'react';
import './DataComparison.css';

function DataComparison({ fruits, onSelectFruit, onClose }) {
  // 简单的对比选择弹窗，数据来自详情页已经加载好的本地 API 结果。
  return (
    <div className="comparison-overlay" onClick={onClose}>
      <div className="comparison-popup" onClick={(event) => event.stopPropagation()}>
        <div className="comparison-header">
          <h2>Choose a food</h2>
          <button className="close-button" type="button" onClick={onClose}>Close</button>
        </div>
        <ul>
          {fruits.map((fruit, index) => (
            <li key={fruit.id || index} onClick={() => onSelectFruit(fruit)}>
              {fruit.displayName || fruit.name}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default DataComparison;

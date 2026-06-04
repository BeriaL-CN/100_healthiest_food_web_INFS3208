import "./App.css";
import { useState } from "react";
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import MapComponent from "./components/MapComponent";
import DataDetails from './components/DataDetails';

function App() {
  // 信息弹窗说明当前数据管线；不会在前端触发外部 API 请求。
  const [showMethodology, setShowMethodology] = useState(false);

  return (
    <div className="App">
      <header className="App-header">
        <div className="title-row">
          <h1>Top 100 Healthiest Food in the World</h1>
          <button
            className="info-button"
            type="button"
            aria-label="Explain food selection rules"
            onClick={() => setShowMethodology(true)}
          >
            i
          </button>
        </div>
      </header>
      {showMethodology && (
        <div className="methodology-overlay" onClick={() => setShowMethodology(false)}>
          <section className="methodology-dialog" onClick={(event) => event.stopPropagation()}>
            <h2>Selection rules</h2>
            <p>
              The current map uses a local Kaggle healthiest-food dataset, then enriches missing
              nutrition fields from the locally downloaded Open Food Facts bulk file.
            </p>
            <ul>
              <li>The base food names, ranking, descriptions, and origin fields come from the Kaggle local CSV.</li>
              <li>Missing fields such as fat, carbohydrates, sugar, salt, saturated fat, and Nutri-Score are filled from a local Open Food Facts bulk export where a good match is available.</li>
              <li>The original Kaggle names and origin regions are kept for readability and stable map placement.</li>
              <li>The Open Food Facts enrichment is generated manually by the Django backend and saved as a local CSV; it is not requested by the frontend.</li>
              <li>Optional Open Food Facts and Wikidata cache files are kept as experiments for future data-source upgrades.</li>
              <li>The frontend reads only Django/local data, so local deployment does not depend on live public APIs.</li>
            </ul>
            <button className="close-methodology" type="button" onClick={() => setShowMethodology(false)}>
              Close
            </button>
          </section>
        </div>
      )}
      <Router>
      <div className="Map">
        <Routes>
          <Route path="/" element={<MapComponent />} />
          <Route path="/data-details" element={<DataDetails />} />
        </Routes>
      </div>
      </Router>
    </div>
  );
}

export default App;

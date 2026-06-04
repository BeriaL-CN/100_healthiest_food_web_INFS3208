const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || "http://localhost:8000";

const fetchFoodData = async ({ source } = {}) => {
  // React 只读取 Django API；Open Food Facts/Wikidata 同步都由后端手动命令完成。
  const query = source ? `?source=${source}` : "";
  const response = await fetch(`${API_BASE_URL}/api/food-data/${query}`);

  if (!response.ok) {
    throw new Error(`Failed to load food data: ${response.status}`);
  }

  return response.json();
};

export const getFruits = async (options) => {
  return fetchFoodData(options);
};

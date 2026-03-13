# INFS3208 Individual Project - Top 100 Healthiest Food Map
## INFS3208 个人项目 - 全球最健康食物产地地图应用

---

### About This Project / 关于这个项目

This is a full-stack web application developed for the INFS3208 course at The University of Queensland. The application displays the world's top 100 healthiest foods on an interactive map, showing their nutritional information and geographical origins.

这是一个为昆士兰大学INFS3208课程开发的全栈Web应用。应用在一个交互式地图上展示全球100种最健康的食物，并显示它们的营养信息和地理来源。

---

### Tech Stack / 技术栈

| Layer | Technology |
|-------|------------|
| Frontend | React, React Router, Leaflet (Map) |
| Backend | Django REST Framework |
| Database | SQLite (development) |
| Container | Docker, Docker Compose |
| Data | CSV (Food Nutrition & Origin Data) |

---

### Features / 功能特点

1. **Interactive Map** - Display food origins on a world map using Leaflet
2. **Data Visualization** - Show nutritional information for each food item
3. **Data Details** - View detailed nutritional values and origin information
4. **REST API** - Django backend serving food data as JSON endpoints

---

### Project Structure / 项目结构

```
INFS3208_Individual_Project/
├── my-app/                    # React Frontend
│   ├── src/
│   │   ├── components/        # React components (Map, DataDetails)
│   │   ├── data/             # Static data files
│   │   └── App.js            # Main app with routing
│   ├── public/                # Static assets
│   ├── package.json           # Node dependencies
│   └── Dockerfile            # Frontend container config
│
├── backend/                   # Django Backend
│   ├── api/                  # Django REST API
│   │   ├── views.py          # API endpoints
│   │   └── urls.py           # URL routing
│   ├── mysite/               # Django project settings
│   ├── requirements.txt      # Python dependencies
│   └── Dockerfile            # Backend container config
│
├── data/                     # CSV data files
│   └── top_100_fruits.csv
│
├── docker-compose.yml        # Docker orchestration
└── README.md                 # This file
```

---

### How to Run / 如何运行

#### Option 1: Using Docker Compose (Recommended)
**使用Docker Compose运行（推荐）**

```bash
# Clone the repository
git clone https://github.com/your-username/INFS3208-Project.git
cd INFS3208-Project

# Start all services
docker-compose up -d

# Access the application
# Frontend: http://localhost
# Backend API: http://localhost:8000
```

---

#### Option 2: Running Locally Without Docker
**不使用Docker本地运行**

**Backend (Django):**
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start server
python manage.py runserver
```

**Frontend (React):**
```bash
cd my-app

# Install dependencies
npm install

# Start development server
npm start
```

The application will be available at `http://localhost:3000`

---

### API Endpoints / API接口

| Endpoint | Description |
|----------|-------------|
| `/api/fruit/` | Get all food data |
| `/api/fruit/{id}/` | Get specific food item |

---

### Reflection / 反思

Through this project, I learned how to integrate a React frontend with a Django backend using REST APIs. I also gained experience with Docker containerization and deployment.

I discovered that using Docker Compose significantly simplifies the deployment process by managing multiple containers as a single service. The Leaflet map integration was particularly interesting as it allowed for visualizing geographical data in an intuitive way.

通过这个项目，我学习如何将React前端与Django后端通过REST API集成。我还获得了Docker容器化和部署的经验。

我发现使用Docker Compose可以通过将多个容器作为单一服务管理来显著简化部署过程。Leaflet地图集成特别有趣，因为它允许以直观的方式可视化地理数据。

---

### Contact / 联系方式

- **Name:** 黄杰鹏 (Jiepeng Huang)
- **Student ID:** 47352580
- **Course:** INFS3208 - Web Information Processing
- **University:** The University of Queensland

---

*Last updated: March 2026*

# Intellix 2.0 Student Information System

An advanced educational management platform built with Streamlit and SQLite, featuring AI-driven insights and comprehensive analytics.

![GitHub badge](https://img.shields.io/badge/Intellix-2.0-blue)

## Key Features

### For Administrators
- 📊 Comprehensive dashboard with student metrics and institutional KPIs
- 👥 Student, teacher, and course management
- 🗓️ Academic session management
- 📝 Course enrollment and teaching assignment
- 📋 Exam scheduling and grading oversight
- 📄 Student transcript viewer with GPA calculations
- 🤖 AI tools for identifying at-risk students and institutional analysis

### For Teachers
- 📈 Enhanced dashboard with comprehensive analytics
- ⚡ Quick stats showing courses, pending grades, attendance and at-risk students
- 📅 Advanced timeline view of recent teaching activities
- ⏰ Detailed upcoming deadlines with exam and assignment tracking
- 🧠 AI-powered student risk analysis with intervention recommendations
- 📊 Performance analytics with grade distribution and attendance correlation
- 📉 Advanced data visualization for student performance tracking
- 💬 Comprehensive messaging system with templates
- 📑 CSV exports for student data and performance reports
- 📌 Class progress analysis and attendance tracking

### For Students
- 🎓 Dashboard showing course status and academic performance
- 📚 Course enrollment and materials access
- 🔢 Grade viewing with GPA calculation
- ✅ Attendance tracking
- 📝 Assignment submission and management
- 📨 Messaging system to communicate with teachers and administrators
- 📆 Study planning tools with AI assistance

## Technologies Used
- **Frontend:** Streamlit for interactive web interface
- **Backend:** Python with SQLite database
- **Data Visualization:** Plotly for interactive charts and graphs
- **AI Components:** Predictive analytics for at-risk identification and performance predictions

## Getting Started

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/intellix-2.0.git
   cd intellix-2.0
   ```

2. Install the requirements
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application
   ```bash
   streamlit run app.py
   ```

## Default Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | admin | admin123 |
| Teacher | teacher1 | teacher123 |
| Student | student1 | student123 |

## Project Structure

```
intellix-2.0/
├── app.py                # Main application entry point
├── database/             # SQLite database and schema
├── pages/                # Streamlit pages for different modules
├── components/           # Reusable UI components
├── models/               # AI models for prediction and planning
├── utils/                # Helper functions and utilities
└── static/               # Static files like images
```

## Screenshots

*Coming soon*

## License

MIT

## Contributors

- [Your Name](https://github.com/yourusername) 
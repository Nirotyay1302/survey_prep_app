AI-Enhanced Survey Dashboard

Environment variables (.env)

Set these in your deployment environment; do not commit secrets:

- FLASK_ENV=production
- SECRET_KEY=replace-with-a-strong-random-string
- DB_HOST=your-mysql-host
- DB_USER=your-mysql-user
- DB_PASS=your-mysql-password
- DB_NAME=survey_app

Local quickstart

1) python -m venv venv && venv\Scripts\activate
2) pip install -r requirements.txt
3) set FLASK_APP=app.py & set FLASK_ENV=development
4) python app.py

Deploy

- Backend: Render/Heroku/Fly.io with Python, set env vars above.
- Static front-end (optional landing): Netlify. Point to `templates` static build or a dedicated front-end.
An interactive Streamlit web application for uploading survey data, configuring analysis parameters, generating insightful reports, and exporting them as HTML or PDF dashboards with colorful visualizations.

🚀 Features
Data Upload: Upload CSV survey datasets directly from the browser.

Configurable Analysis: Set parameters for data analysis through an intuitive form.

Automated Insights: Generates analysis reports enriched with charts, graphs, and summary tables.

Dashboard Export: Download reports as HTML or PDF files.

Colorful UI: Attractive, user-friendly interface for easy interpretation.

Cross-Platform: Runs on any system with Python and Streamlit installed.

📊 Example Dashboard Sections
Application name & date at the top.

Summary statistics of survey results.

Visualizations (bar charts, pie charts, etc.).

Highlighted key insights.

Download links for HTML & PDF reports.

🛠 Installation
Clone this repository

bash
Copy code
git clone https://github.com/yourusername/ai-enhanced-survey-dashboard.git
cd ai-enhanced-survey-dashboard
Install dependencies

bash
Copy code
pip install -r requirements.txt
Run the application

bash
Copy code
streamlit run app.py
📂 Project Structure
bash
Copy code
├── app.py                  # Main Streamlit application
├── requirements.txt        # Python dependencies
├── report_templates/       # HTML report templates
├── sample_data/            # Example CSV datasets
└── README.md               # Project documentation
Tech Stack 🛠️
Python  3.8+ 🐍

Streamlit for UI

Matplotlib & Seaborn for charts

Pandas for data wrangling

pdfkit / WeasyPrint for PDF generation

Install all dependencies using:

bash
Copy code
pip install -r requirements.txt
📥 How to Use
Upload your CSV survey dataset.

Fill out the analysis configuration form.

Click Generate Report.

Preview the dashboard in the browser.

Download it as HTML or PDF.


📜 License
This project is licensed under the MIT License. You are free to use, modify, and distribute it.


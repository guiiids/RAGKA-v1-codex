# Agilent Chatbot Tools Dashboard

A comprehensive web application for managing and optimizing AI chatbot prompts, featuring evaluation tools, enhancement capabilities, and feedback analytics. Built with Flask, Tailwind CSS, and following Agilent Technologies design guidelines.

![Dashboard Preview](docs/dashboard-preview.png)

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- pip (Python package installer)
- Modern web browser (Chrome, Firefox, Safari, Edge)

### Installation

1. **Clone or Download the Project**
   ```bash
   # If you have the zip file, extract it
   unzip agilent_chatbot_tools.zip
   cd agilent_chatbot_tools
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Application**
   ```bash
   python app.py
   ```

4. **Access the Dashboard**
   Open your web browser and navigate to:
   ```
   http://localhost:5001
   ```

## 📁 Project Structure

```
agilent_chatbot_tools/
├── app.py                          # Main Flask application
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── templates/                      # HTML templates
│   ├── base.html                  # Base template with navigation
│   ├── index.html                 # Main dashboard
│   ├── prompt_evaluator.html      # Prompt evaluation tool
│   ├── prompt_lab.html            # Prompt enhancement lab
│   └── feedback_insights.html     # Analytics dashboard
├── static/                        # Static assets (CSS, JS, Images)
│   ├── css/                       # Custom stylesheets
│   ├── js/                        # JavaScript files
│   └── images/                    # Image assets
├── docs/                          # Documentation
└── scripts/                       # Utility scripts
```

## 🎯 Features Overview

### 1. Main Dashboard
The central hub providing an overview of all tools and key metrics.

**Features:**
- **Key Metrics Display**: Total evaluations, success rate, active prompts, feedback items
- **Tool Navigation Cards**: Quick access to all three main tools
- **Recent Activity Feed**: Latest evaluations, enhancements, and feedback
- **Quick Start Guide**: Step-by-step instructions for new users
- **Responsive Design**: Works seamlessly on desktop, tablet, and mobile

**How to Use:**
1. Navigate to the main dashboard at `http://localhost:5001`
2. View key metrics at the top of the page
3. Click on any tool card to access specific functionality
4. Check recent activity for latest updates

### 2. Prompt Evaluator
Analyze and score prompts for optimal AI performance.

**Features:**
- **Prompt Analysis**: Comprehensive evaluation of prompt quality
- **Scoring System**: 0-100 point scoring with detailed breakdown
- **Evaluation Criteria**: 
  - Clarity & Specificity (85/100)
  - Completeness (92/100)
  - Context & Examples (78/100)
  - Structure & Format (85/100)
- **Detailed Feedback**: Strengths and improvement suggestions
- **Export Options**: Copy results or enhance in Prompt Lab

**How to Use:**
1. Navigate to Prompt Evaluator
2. Enter your prompt in the text area
3. Select evaluation focus areas (optional)
4. Click "Evaluate Prompt"
5. Review the detailed analysis and scoring
6. Use "Copy Results" or "Enhance in Lab" buttons

**Example Evaluation:**
```
Input: "Write an email about project status."
Output: Overall Score 85/100
- Clarity & Specificity: 85/100
- Completeness: 92/100
- Context & Examples: 78/100
- Structure & Format: 85/100

Improvements:
• Added request for specific examples
• Included context requirement
• Improved clarity of instructions
```

### 3. Prompt Lab
Enhance, rephrase, and optimize prompts with AI-powered tools.

**Features:**
- **Three Enhancement Tools**:
  - **Enhance**: Improve prompt quality and specificity
  - **Rephrase**: Change style while preserving intent
  - **Evaluate**: Quick evaluation integration
- **Enhancement Options**:
  - Type: General, Clarity, Specificity, Context, Examples
  - Style: Professional, Casual, Technical, Creative, Concise
  - Preserve original intent
  - Add examples automatically
- **Template Library**: Pre-built templates for common use cases
- **Recent Prompts**: Quick access to previously used prompts
- **Quick Actions**: Save, compare, and load templates

**How to Use:**
1. Navigate to Prompt Lab
2. Enter your original prompt
3. Choose enhancement type and style options
4. Click "Enhance", "Rephrase", or "Evaluate"
5. Review the results and use "Copy" or "Use This"
6. Access templates via "Load Template" for quick starts

**Enhancement Example:**
```
Original: "Write an email about project status."
Enhanced: "Write a professional email to [recipient] about [project name] status. Include current progress, any challenges encountered, next steps, and expected completion date. Use a professional tone and ensure the email is clear and actionable."

Improvements Made:
• Added request for specific examples
• Included context requirement
• Improved clarity of instructions
```

### 4. Feedback Insights Dashboard
Comprehensive analytics for tracking feedback and performance trends.

**Features:**
- **Key Metrics**:
  - Total Responses: 1,247 (↗ 12.5% vs last month)
  - Positive Feedback: 892 (↗ 8.2% vs last month)
  - Negative Feedback: 355 (↘ 3.1% vs last month)
  - Satisfaction Rate: 71.5% (↗ 5.7% vs last month)
- **Interactive Charts**:
  - Feedback Trends: Line chart showing positive/negative trends over time
  - Distribution: Doughnut chart showing feedback breakdown
- **Common Issues Analysis**: Top 5 issues with percentages and report counts
- **Recent Feedback**: Real-time feed of latest feedback with sentiment
- **Advanced Filtering**: Date range, feedback type, and source filters
- **Export Options**: CSV, PDF, and scheduled reports

**How to Use:**
1. Navigate to Feedback Insights
2. Review key metrics at the top
3. Analyze trends using interactive charts
4. Check common issues for improvement areas
5. Use filters to narrow down data
6. Export reports using the export buttons

**Common Issues Example:**
1. Response too generic (25.1% of negative feedback - 89 reports)
2. Missing context (18.9% of negative feedback - 67 reports)
3. Incorrect information (12.7% of negative feedback - 45 reports)
4. Too verbose (9.6% of negative feedback - 34 reports)
5. Unclear instructions (7.9% of negative feedback - 28 reports)

## 🎨 Design & Branding

### Agilent Style Guide Implementation
- **Primary Color**: Agilent Blue (#0073E6)
- **Success Color**: Green (#28A745)
- **Error Color**: Red (#DC3545)
- **Typography**: Clean, professional fonts with proper hierarchy
- **Layout**: Modern grid system with consistent spacing
- **Icons**: SVG icons with scientific/technical aesthetic

### Responsive Design
- **Desktop**: Full-featured layout with side-by-side panels
- **Tablet**: Stacked layout with touch-friendly controls
- **Mobile**: Single-column layout with collapsible navigation

## 🔧 Technical Details

### Backend (Flask)
- **Framework**: Flask 2.3.3 with CORS support
- **API Endpoints**:
  - `GET /` - Main dashboard
  - `GET /prompt-evaluator` - Evaluation tool
  - `GET /prompt-lab` - Enhancement lab
  - `GET /feedback-insights` - Analytics dashboard
  - `POST /api/evaluate-prompt` - Prompt evaluation
  - `POST /api/enhance-prompt` - Prompt enhancement
  - `POST /api/rephrase-prompt` - Prompt rephrasing
  - `GET /api/feedback-data` - Feedback analytics data

### Frontend
- **Styling**: Tailwind CSS for responsive design
- **JavaScript**: Vanilla JS for interactivity
- **Charts**: Chart.js for data visualization
- **Icons**: SVG icons for scalability

### Dependencies
```
Flask==2.3.3
Flask-CORS==4.0.0
requests==2.31.0
```

## 🚀 Deployment Options

### Development Server (Default)
```bash
python app.py
# Access at http://localhost:5001
```

### Production with Gunicorn
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5001
CMD ["python", "app.py"]
```

### Environment Variables
- `FLASK_ENV`: Set to 'production' for production deployment
- `PORT`: Port number (default: 5001)
- `HOST`: Host address (default: 0.0.0.0)

## 🔒 Security Features

- **Input Validation**: Client-side and server-side validation
- **CORS Protection**: Configured for secure cross-origin requests
- **XSS Prevention**: Proper HTML escaping and sanitization
- **Error Handling**: Graceful error handling without exposing internals

## 📱 Browser Compatibility

- **Chrome**: 90+
- **Firefox**: 88+
- **Safari**: 14+
- **Edge**: 90+
- **Mobile**: iOS Safari 14+, Chrome Mobile 90+

## 🛠️ Customization

### Adding New Features
1. Create new route in `app.py`
2. Add corresponding HTML template in `templates/`
3. Update navigation in `base.html`
4. Add any required JavaScript functionality

### Modifying Styles
1. Update Tailwind classes in HTML templates
2. Add custom CSS in `static/css/` if needed
3. Modify color scheme in `base.html` CSS variables

### API Integration
1. Add new endpoints in `app.py`
2. Update frontend JavaScript to call new endpoints
3. Handle responses and update UI accordingly

## 🐛 Troubleshooting

### Common Issues

**Port Already in Use**
```bash
# Kill existing process
pkill -f "python app.py"
# Or use a different port
export PORT=5002
python app.py
```

**Dependencies Not Installing**
```bash
# Upgrade pip
pip install --upgrade pip
# Install with verbose output
pip install -r requirements.txt -v
```

**Charts Not Displaying**
- Ensure JavaScript is enabled in browser
- Check browser console for errors
- Verify Chart.js CDN is accessible

### Performance Optimization
- Enable browser caching for static assets
- Minify CSS and JavaScript for production
- Use a reverse proxy (nginx) for production deployment
- Implement database caching for analytics data

## 📞 Support

For technical support or questions:
1. Check the troubleshooting section above
2. Review the browser console for JavaScript errors
3. Ensure all dependencies are properly installed
4. Verify Python version compatibility (3.8+)

## 📄 License

This project is created for Agilent Technologies and follows their internal development guidelines and branding standards.

## 🔄 Version History

- **v1.0.0** - Initial release with all core features
  - Prompt Evaluator with scoring system
  - Prompt Lab with enhancement tools
  - Feedback Insights dashboard
  - Responsive Agilent-branded design
  - Complete API integration

---

**Built with ❤️ for Agilent Technologies**


# AI Agent Assistant

A sophisticated AI-powered assistant that can understand natural language instructions and perform tasks across different domains using specialized agents.

## 🌟 Features

- **Natural Language Understanding**: Process and understand complex instructions
- **Task Delegation**: Automatically delegate tasks to specialized agents
- **WebSocket Communication**: Real-time updates and progress tracking
- **Modular Architecture**: Easy to extend with new agents and capabilities
- **Responsive UI**: Clean and intuitive user interface

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Node.js 16+
- npm or yarn
- Google API Key (for Gemini AI)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/ai-agent-assistant.git
   cd ai-agent-assistant
   ```

2. **Set up the backend**
   ```bash
   # Create and activate virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   
   # Install dependencies
   cd backend
   pip install -r requirements.txt
   
   # Create .env file
   cp .env.example .env
   # Edit .env with your Google API key
   ```

3. **Set up the frontend**
   ```bash
   cd ../frontend
   npm install
   ```

### Configuration

Create a `.env` file in the `backend` directory with the following variables:

```env
GOOGLE_API_KEY=your_google_api_key_here
DEBUG=true
CORS_ORIGINS=http://localhost:3000
```

## 🏃‍♂️ Running the Application

### Development Mode

1. **Start the backend server**
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

2. **Start the frontend development server**
   ```bash
   cd ../frontend
   npm start
   ```

The application will be available at `http://localhost:3000`

### Production Build

1. **Build the frontend**
   ```bash
   cd frontend
   npm run build
   ```

2. **Run the production server**
   ```bash
   cd ../backend
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## 🧩 Project Structure

```
ai-agent-assistant/
├── backend/                  # Backend server
│   ├── app/
│   │   ├── agents/          # Specialized agent implementations
│   │   ├── utils/           # Utility functions
│   │   ├── config.py        # Configuration settings
│   │   ├── main.py          # Main FastAPI application
│   │   └── __init__.py
│   ├── requirements.txt     # Python dependencies
│   └── .env.example        # Example environment variables
│
└── frontend/                # Frontend React application
    ├── public/             # Static files
    ├── src/                # Source files
    │   ├── components/     # React components
    │   ├── App.js          # Main App component
    │   └── index.js        # Entry point
    ├── package.json        # Node.js dependencies
    └── tailwind.config.js  # Tailwind CSS configuration
```

## 🤖 Available Agents

- **Planner Agent**: Main agent that understands instructions and delegates tasks
- **Scheduler Agent**: Handles calendar and scheduling tasks
- **Email Agent**: Manages email-related operations
- **Notification Agent**: Handles system notifications

## 🌐 API Documentation

Once the backend server is running, you can access:

- **Interactive API Docs**: `http://localhost:8000/docs`
- **Alternative API Docs**: `http://localhost:8000/redoc`

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest
```

### Frontend Tests
```bash
cd frontend
npm test
```

## 🛠️ Built With

- **Backend**:
  - FastAPI
  - Python 3.8+
  - Google Gemini AI
  - WebSockets

- **Frontend**:
  - React
  - Tailwind CSS
  - WebSocket client

## 🤝 Contributing

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://reactjs.org/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Google Gemini](https://ai.google/)

---

<div align="center">
  <p>Made with ❤️ by Your Name</p>
</div>

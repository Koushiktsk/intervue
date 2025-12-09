# 🎯 Intervue

An AI-powered voice interview practice application that helps you prepare for job interviews with real-time feedback and comprehensive performance analysis.

## ✨ Features

- **🎤 Voice Interaction**: Real interview experience with voice questions and answers
- **🤖 AI-Powered**: Uses Google Gemini AI for intelligent question generation and evaluation
- **⚡ Instant Feedback**: Get conversational responses after each answer
- **📊 Detailed Reports**: Comprehensive analysis with scores and improvement suggestions
- **⏱️ Timed Sessions**: Practice with customizable interview durations (3-60 minutes)
- **🎯 Role-Specific**: Tailored questions for different job roles and experience levels
- **🔊 Text-to-Speech**: AI interviewer speaks questions naturally using Windows SAPI
- **🎙️ Speech Recognition**: Automatic transcription of your spoken answers

## 🚀 Supported Roles

1. **Software Engineer** - Algorithms, System Design, Coding
2. **Sales Representative** - Communication, Persuasion, Closing
3. **Retail Associate** - Customer Service, Problem Solving
4. **Product Manager** - Strategy, Stakeholder Management
5. **Data Analyst** - SQL, Analytics, Data Interpretation

## 📋 Experience Levels

- **Fresher/Entry Level** (0-2 years) - Basic concepts and definitions
- **Mid-Level** (2-5 years) - Practical application and problem-solving
- **Senior** (5+ years) - Complex design and architecture

## 🛠️ Technology Stack

### Backend
- **Flask** - Python web framework
- **Google Gemini AI** - Question generation and evaluation
- **SpeechRecognition** - Voice input processing
- **Windows SAPI** - Text-to-speech output
- **PyAudio** - Audio input/output handling

### Frontend
- **HTML5** - Structure
- **CSS3** - Modern, responsive styling
- **Vanilla JavaScript** - Interactive functionality
- **Google Fonts (Inter)** - Typography

## 📦 Installation

### Prerequisites

- Python 3.8 or higher
- Windows OS (for SAPI text-to-speech)
- Microphone and speakers/headphones
- Google Gemini API key

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd interview-practice-partner
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Set Up Environment Variables

**Important: Keep your API key secure!**

1. Copy the example environment file:
   ```bash
   copy .env.example .env
   ```
   (On Linux/Mac: `cp .env.example .env`)

2. Open the `.env` file and add your Gemini API key:
   ```env
   GEMINI_API_KEY=your_actual_api_key_here
   ```

3. **Never commit the `.env` file to version control!** (It's already in `.gitignore`)

**To get a Gemini API key:**
1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the generated key
5. Paste it into your `.env` file (replace `your_actual_api_key_here`)

> ⚠️ **Security Note**: The `.env` file contains sensitive information. Never share it publicly or commit it to Git. The `.gitignore` file is configured to protect it automatically.

### Step 5: Run the Application

```bash
python app.py
```

The application will start on `http://127.0.0.1:5000`

## 🎮 How to Use

### 1. Welcome Screen
- Enter your name
- Click "Start Your Practice"

### 2. Choose Your Role
- Select the job role you're preparing for
- Each role has specific question topics

### 3. Select Experience Level
- Choose your experience level
- Questions will be tailored to your level

### 4. Configure Interview
- Select interview duration (3-60 minutes)
- Review the setup
- Click "Launch Interview"

### 5. During the Interview
- **Listen** to the AI interviewer's question
- **Press Enter** when ready to answer
- **Speak** your answer (stops automatically after 3 seconds of silence)
- Receive **instant conversational feedback**
- Continue to the next question

### 6. Interview Controls
- **Timer**: Shows remaining time (changes color as time runs low)
- **Question Counter**: Tracks current question number
- **Quit Button**: End interview early and get report

### 7. Final Report
- **Overall Score**: Average score across all questions
- **Question-by-Question Breakdown**: Individual scores and answers
- **Comprehensive Feedback**: Strengths, weaknesses, and improvement tips
- **Color-Coded Scores**: 
  - 🟢 Green (7-10): Excellent
  - 🟠 Orange (5-6.9): Good
  - 🔴 Red (0-4.9): Needs Improvement

## ⚙️ Configuration

### Adjust Speech Recognition Settings

In `web_interview.py`, modify the recognizer settings:

```python
self.recognizer.energy_threshold = 4000  # Microphone sensitivity
self.recognizer.pause_threshold = 3.0    # Silence duration to stop (seconds)
```

### Adjust Text-to-Speech Settings

In `web_interview.py`, modify the speaker rate:

```python
self.speaker = SafeSpeaker(rate=2)  # Speech rate (0-10, default: 2)
```

### Customize Interview Duration Options

In `index.html`, modify the duration buttons:

```html
<button class="duration-btn" onclick="selectDuration(YOUR_MINUTES, event)">
    <span class="duration-time">YOUR_MINUTES</span>
    <span class="duration-label">minutes</span>
</button>
```


## 📁 Project Structure

```
interview-practice-partner/
├── app.py                  # Flask backend server
├── web_interview.py        # Interview agent logic
├── index.html              # Main HTML structure
├── style.css               # Styling and layout
├── script.js               # Frontend JavaScript
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (create from .env.example)
├── .env.example            # Example environment file (safe to commit)
├── .gitignore              # Git ignore rules (protects .env)
├── README.md               # This file
└── venv/                   # Virtual environment (created during setup)
```

---

**Happy Practicing! Good luck with your interviews! 🚀**

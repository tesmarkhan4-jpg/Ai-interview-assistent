import json
import os
import datetime

class HistoryManager:
    def __init__(self):
        # Use APPDATA for user-writable files
        self.data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), "StealthHUD")
        os.makedirs(self.data_dir, exist_ok=True)
            
        self.history_file = os.path.join(self.data_dir, "interviews_history.json")
        self.history = self.load_history()

    def load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_interview(self, username, summary_data):
        if username not in self.history:
            self.history[username] = []
        
        entry = {
            "id": datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
            "date": datetime.datetime.now().strftime("%d %B %Y, %I:%M %p"),
            "summary": summary_data.get("summary", "No summary available."),
            "salary_recommendation": summary_data.get("salary", "N/A"),
            "market_analysis": summary_data.get("market", "N/A"),
            "client_needs": summary_data.get("client_needs", "N/A"),
            "project_scope": summary_data.get("project_scope", "N/A"),
            "technical_breakdown": summary_data.get("technical_breakdown", "N/A"),
            "job_requirements": summary_data.get("job_requirements", "N/A"),
            "full_transcript": summary_data.get("full_transcript", "No transcript recorded.")
        }
        
        self.history[username].insert(0, entry) # Most recent first
        
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=4)
        
        return entry["id"]

    def get_user_history(self, username):
        return self.history.get(username, [])

    def generate_summary_html(self, interview_id):
        # Find the interview
        found = None
        for user in self.history:
            for entry in self.history[user]:
                if entry["id"] == interview_id:
                    found = entry
                    break
            if found: break
            
        if not found: return "Interview not found."
        
    def generate_summary_html(self, interview_id):
        found = None
        for user in self.history:
            for entry in self.history[user]:
                if entry["id"] == interview_id:
                    found = entry
                    break
            if found: break
            
        if not found: return "Interview not found."

        # Format transcript line by line
        formatted_transcript = ""
        lines = found['full_transcript'].split('\n')
        for line in lines:
            if line.strip():
                if line.startswith("USER:"):
                    formatted_transcript += f'<div style="color: #0f172a; margin-bottom: 12px; padding-left: 10px; border-left: 3px solid #e2e8f0;"><b>Interviewer:</b> {line[5:]}</div>'
                elif line.startswith("AI:"):
                    formatted_transcript += f'<div style="color: #059669; margin-bottom: 12px; padding-left: 10px; border-left: 3px solid #10b981;"><b>StealthHUD (Suggestion):</b> {line[3:]}</div>'
                else:
                    formatted_transcript += f'<div style="color: #64748b; margin-bottom: 8px; font-style: italic;">{line}</div>'
        
        html = f"""
        <html>
        <head>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
            <style>
                body {{ 
                    font-family: 'Inter', sans-serif; 
                    background: #f8fafc; 
                    color: #1e293b; 
                    padding: 50px 20px; 
                    line-height: 1.7; 
                }}
                .container {{ 
                    max-width: 850px; 
                    margin: auto; 
                    background: #ffffff; 
                    padding: 50px; 
                    border-radius: 20px; 
                    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.05);
                    border: 1px solid #e2e8f0;
                }}
                h1 {{ color: #0f172a; font-weight: 800; font-size: 32px; margin: 10px 0; }}
                .date {{ color: #64748b; font-size: 15px; margin-bottom: 40px; font-weight: 500; }}
                .badge {{ 
                    display: inline-block; 
                    background: #ecfdf5; 
                    color: #059669; 
                    padding: 6px 14px; 
                    border-radius: 8px; 
                    font-weight: 700; 
                    font-size: 12px; 
                    text-transform: uppercase; 
                    letter-spacing: 0.5px;
                }}
                .section {{ 
                    margin-bottom: 40px; 
                    padding-bottom: 30px;
                    border-bottom: 1px solid #f1f5f9;
                }}
                .section:last-child {{ border-bottom: none; }}
                .section-title {{ 
                    color: #059669; 
                    font-weight: 800; 
                    margin-bottom: 18px; 
                    text-transform: uppercase; 
                    letter-spacing: 1.2px; 
                    font-size: 12px; 
                    display: flex;
                    align-items: center;
                }}
                .section-title::after {{
                    content: "";
                    height: 1px;
                    background: #e2e8f0;
                    flex: 1;
                    margin-left: 15px;
                }}
                .content {{ font-size: 16px; color: #334155; white-space: pre-wrap; }}
                .roadmap {{ background: #f0fdf4; padding: 25px; border-radius: 12px; border: 1px solid #dcfce7; color: #166534; font-weight: 500; }}
                .transcript-box {{ 
                    background: #fdfdfd; 
                    padding: 25px; 
                    border-radius: 12px; 
                    border: 1px solid #f1f5f9;
                    font-size: 14px; 
                    max-height: 500px; 
                    overflow-y: auto; 
                    line-height: 1.5;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="badge">Tactical Interview Intelligence</div>
                <h1>Intelligence Report</h1>
                <div class="date">{found['date']}</div>
                
                <div class="section">
                    <div class="section-title">Executive Summary</div>
                    <div class="content">{found['summary']}</div>
                </div>
                
                <div class="section">
                    <div class="section-title">Client Needs & Goals</div>
                    <div class="content">{found['client_needs']}</div>
                </div>
                
                <div class="section">
                    <div class="section-title">Technical Roadmap</div>
                    <div class="roadmap">{found['technical_breakdown']}</div>
                </div>

                <div class="section">
                    <div class="section-title">Strategic Strategy</div>
                    <div class="content"><b>Recommendation:</b> {found['salary_recommendation']}</div>
                    <div style="font-size: 13px; margin-top: 10px; color: #64748b;">Market Context: {found['market_analysis']}</div>
                </div>

                <div class="section">
                    <div class="section-title">Conversation Log</div>
                    <div class="transcript-box">
                        {formatted_transcript}
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html

history_manager = HistoryManager()

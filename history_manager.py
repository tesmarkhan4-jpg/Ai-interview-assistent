import json
import os
import datetime

class HistoryManager:
    def __init__(self):
        import sys
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
            
        self.history_file = os.path.join(application_path, "interviews_history.json")
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
            "client_needs": summary_data.get("needs", "N/A")
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
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Inter', sans-serif; background: #0F172A; color: #E2E8F0; padding: 40px; line-height: 1.6; }}
                .container {{ max-width: 800px; margin: auto; background: rgba(30, 41, 59, 0.5); padding: 40px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.1); }}
                h1 {{ color: #00E676; letter-spacing: 2px; }}
                .tag {{ display: inline-block; background: #D4AF37; color: #1A2E2A; padding: 5px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; margin-bottom: 20px; }}
                .section {{ margin-bottom: 30px; }}
                .section-title {{ color: #00B0FF; font-weight: bold; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px; }}
                .salary-box {{ background: rgba(0, 230, 118, 0.1); border: 1px solid #00E676; padding: 20px; border-radius: 15px; text-align: center; }}
                .salary-value {{ font-size: 24px; font-weight: 900; color: #00E676; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="tag">INTERVIEW INSIGHT REPORT</div>
                <h1>{found['date']}</h1>
                
                <div class="section">
                    <div class="section-title">Concise Summary</div>
                    <div>{found['summary']}</div>
                </div>
                
                <div class="section">
                    <div class="section-title">Client Requirements & Needs</div>
                    <div>{found['client_needs']}</div>
                </div>

                <div class="section">
                    <div class="section-title">Market Analysis</div>
                    <div>{found['market_analysis']}</div>
                </div>

                <div class="salary-box">
                    <div class="section-title" style="color: #00E676;">Recommended Strategy (Win the Job)</div>
                    <div class="salary-value">{found['salary_recommendation']}</div>
                    <div style="font-size: 11px; margin-top: 5px; color: rgba(255,255,255,0.5);">Calculated to be competitive yet lower than standard market rates to ensure selection.</div>
                </div>
            </div>
        </body>
        </html>
        """
        return html

history_manager = HistoryManager()

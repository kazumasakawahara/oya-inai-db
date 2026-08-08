import os
import json
from datetime import datetime
from agno.tools import Toolkit
from skills.report_generator.excel_exporter import export_client_data_to_excel

class ReportToolkit(Toolkit):
    def __init__(self):
        super().__init__(name="report_toolkit")
        self.register(self.generate_excel_report)

    def generate_excel_report(self, client_name: str) -> str:
        """
        Generate a comprehensive Excel report for the client, including profile, care preferences, and support history.
        
        Args:
            client_name: Name of the client.
            
        Returns:
            Path to the generated Excel file.
        """
        try:
            path = export_client_data_to_excel(client_name)
            return f"Report generated successfully: {path}"
        except Exception as e:
            return f"Failed to generate report: {e}"

import subprocess
import os
import pandas as pd
import sqlite3
import json
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Güvenlik kontrollerini geçici olarak devre dışı bırak
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

class ProcessExecutor:
    @staticmethod
    def get_gmail_service():
        SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send']
        creds = None
        
        # Token dosyasını kontrol et
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        # Eğer token yoksa veya geçersizse yeni token al
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    return None, "credentials.json dosyası bulunamadı. Lütfen Google Cloud Console'dan indirip projenin kök dizinine ekleyin."
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=8080)
            
            # Token'ı kaydet
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        return build('gmail', 'v1', credentials=creds), None

    @staticmethod
    def send_email(service, to, subject, body, cc=None):
        try:
            message = MIMEMultipart()
            message['to'] = to
            message['subject'] = subject
            if cc:
                message['cc'] = cc

            msg = MIMEText(body)
            message.attach(msg)

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()

            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def execute_mail_check(variables=None):
        try:
            # Gmail servisini al
            service, error = ProcessExecutor.get_gmail_service()
            if error:
                return {
                    'success': False,
                    'output': None,
                    'error': error
                }
            
            sent_mails = []
            if variables:
                # 5 mail setini kontrol et
                for i in range(1, 6):
                    active = next((var for var in variables if var['name'] == f'mail_{i}_active'), None)
                    
                    if active and active['value'] == 'true':
                        to = next((var['value'] for var in variables if var['name'] == f'mail_{i}_to'), None)
                        cc = next((var['value'] for var in variables if var['name'] == f'mail_{i}_cc'), None)
                        subject = next((var['value'] for var in variables if var['name'] == f'mail_{i}_subject'), None)
                        body = next((var['value'] for var in variables if var['name'] == f'mail_{i}_body'), None)
                        
                        if to and subject and body:  # CC opsiyonel
                            success, error = ProcessExecutor.send_email(service, to, subject, body, cc)
                            sent_mails.append({
                                'index': i,
                                'to': to,
                                'cc': cc,
                                'subject': subject,
                                'success': success,
                                'error': error
                            })
            
            return {
                'success': True,
                'output': sent_mails,
                'error': None
            }
        except Exception as e:
            return {
                'success': False,
                'output': None,
                'error': str(e)
            }

    @staticmethod
    def execute_python_script(file_path):
        try:
            result = subprocess.run(['python', file_path], 
                                 capture_output=True, 
                                 text=True, 
                                 check=True)
            return {
                'success': True,
                'output': result.stdout,
                'error': result.stderr
            }
        except subprocess.CalledProcessError as e:
            return {
                'success': False,
                'output': e.stdout,
                'error': e.stderr
            }

    @staticmethod
    def execute_excel_file(file_path):
        try:
            # Excel dosyasını pandas ile okuma
            df = pd.read_excel(file_path)
            # Burada Excel dosyası ile ilgili işlemler yapılabilir
            return {
                'success': True,
                'output': f"Excel dosyası başarıyla işlendi. Satır sayısı: {len(df)}",
                'error': None
            }
        except Exception as e:
            return {
                'success': False,
                'output': None,
                'error': str(e)
            }

    @staticmethod
    def execute_sql_script(file_path, db_path):
        try:
            # SQL dosyasını okuma
            with open(file_path, 'r') as file:
                sql_script = file.read()

            # SQLite veritabanına bağlanma ve scripti çalıştırma
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.executescript(sql_script)
            conn.commit()
            conn.close()

            return {
                'success': True,
                'output': "SQL script başarıyla çalıştırıldı",
                'error': None
            }
        except Exception as e:
            return {
                'success': False,
                'output': None,
                'error': str(e)
            }

    @staticmethod
    def execute_step(step_type, file_path, **kwargs):
        if step_type == 'python_script':
            return ProcessExecutor.execute_python_script(file_path)
        elif step_type == 'excel_file':
            return ProcessExecutor.execute_excel_file(file_path)
        elif step_type == 'sql_script':
            db_path = kwargs.get('db_path', 'processes.db')
            return ProcessExecutor.execute_sql_script(file_path, db_path)
        elif step_type == 'mail':
            return ProcessExecutor.execute_mail_check()
        else:
            return {
                'success': False,
                'output': None,
                'error': f"Desteklenmeyen adım tipi: {step_type}"
            } 
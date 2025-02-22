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

class ProcessExecutor:
    @staticmethod
    def get_gmail_service():
        SCOPES = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.send'
        ]
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
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', SCOPES)
                    # Önce hangi portu kullanacağımızı belirleyelim
                    port = 8085  # Sabit bir port kullanıyoruz
                    redirect_uri = f'http://localhost:{port}/'
                    print(f"\n[ÖNEMLİ] Lütfen Google Cloud Console'da şu yönlendirme URI'sini ekleyin:\n{redirect_uri}\n")
                    creds = flow.run_local_server(port=port)
                except Exception as e:
                    return None, f"OAuth hatası: {str(e)}\nLütfen yukarıdaki yönlendirme URI'sini Google Cloud Console'a eklediğinizden emin olun."
            
            # Token'ı kaydet
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        return build('gmail', 'v1', credentials=creds), None

    @staticmethod
    def send_mail(variables):
        try:
            # Mail konfigürasyonunu kontrol et
            if not variables:
                raise Exception('Mail konfigürasyonu bulunamadı')
            
            # Zorunlu alanları kontrol et
            if not variables.get('to'):
                raise Exception('En az bir alıcı belirtilmeli')
            if not variables.get('subject'):
                raise Exception('Mail konusu belirtilmeli')
            if not variables.get('body'):
                raise Exception('Mail içeriği belirtilmeli')
            
            # Aktif değilse gönderme
            if not variables.get('active', False):
                return {
                    'success': True,
                    'output': 'Mail gönderimi pasif durumda',
                    'error': None
                }
            
            # Gmail servisini al
            service, error = ProcessExecutor.get_gmail_service()
            if error:
                return {
                    'success': False,
                    'output': None,
                    'error': error
                }
            
            # Mail mesajını oluştur
            message = MIMEMultipart()
            message['to'] = ','.join(variables['to'])
            if variables.get('cc'):
                message['cc'] = ','.join(variables['cc'])
            message['subject'] = variables['subject']
            
            # Mail içeriğini ekle
            msg = MIMEText(variables['body'])
            message.attach(msg)
            
            # Base64 formatına çevir
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            try:
                # Maili gönder
                service.users().messages().send(
                    userId='me',
                    body={'raw': raw}
                ).execute()
                
                return {
                    'success': True,
                    'output': 'Mail başarıyla gönderildi',
                    'error': None
                }
            except Exception as e:
                return {
                    'success': False,
                    'output': None,
                    'error': f'Mail gönderilirken hata oluştu: {str(e)}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'output': None,
                'error': str(e)
            }

    @staticmethod
    def execute_mail_check():
        try:
            # Gmail servisini al
            service, error = ProcessExecutor.get_gmail_service()
            if error:
                return {
                    'success': False,
                    'output': None,
                    'error': error
                }
            
            # Son 10 maili al
            results = service.users().messages().list(
                userId='me',
                maxResults=10,
                labelIds=['INBOX']
            ).execute()
            
            messages = results.get('messages', [])
            mails = []
            
            for message in messages:
                msg = service.users().messages().get(
                    userId='me',
                    id=message['id'],
                    format='full'
                ).execute()
                
                headers = msg['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'Konu Yok')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Gönderen Bilinmiyor')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
                
                # Mail içeriğini al
                if 'parts' in msg['payload']:
                    body = ''
                    for part in msg['payload']['parts']:
                        if part['mimeType'] == 'text/plain':
                            body = base64.urlsafe_b64decode(
                                part['body']['data']
                            ).decode('utf-8')
                            break
                else:
                    body = base64.urlsafe_b64decode(
                        msg['payload']['body']['data']
                    ).decode('utf-8') if 'data' in msg['payload']['body'] else ''
                
                mails.append({
                    'subject': subject,
                    'sender': sender,
                    'received': date,
                    'body': body[:200] + '...' if len(body) > 200 else body
                })
            
            return {
                'success': True,
                'output': mails,
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
            if kwargs.get('variables'):
                # Birden fazla mail konfigürasyonu olabilir
                mail_configs = kwargs['variables']
                if not isinstance(mail_configs, list):
                    mail_configs = [mail_configs]
                
                results = []
                success = True
                error_messages = []
                
                for config in mail_configs:
                    result = ProcessExecutor.send_mail(config)
                    results.append(result)
                    if not result['success']:
                        success = False
                        error_messages.append(result['error'])
                
                if success:
                    return {
                        'success': True,
                        'output': 'Tüm mailler başarıyla gönderildi',
                        'error': None
                    }
                else:
                    return {
                        'success': False,
                        'output': None,
                        'error': f'Mail gönderimi sırasında hatalar oluştu: {", ".join(error_messages)}'
                    }
            return ProcessExecutor.execute_mail_check()
        else:
            return {
                'success': False,
                'output': None,
                'error': f"Desteklenmeyen adım tipi: {step_type}"
            } 
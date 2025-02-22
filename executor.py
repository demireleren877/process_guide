import subprocess
import os
import pandas as pd
import sqlite3
import json
from datetime import datetime
import win32com.client
import pythoncom

class ProcessExecutor:
    _instance = None
    _db_path = None  # Veritabanı yolu için static değişken

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_db_path(cls, db_path):
        """Veritabanı yolunu ayarla"""
        cls._db_path = db_path

    @classmethod
    def _check_db_process_status(cls):
        """Veritabanından süreç durumunu kontrol et"""
        if not cls._db_path:
            return False
        
        try:
            conn = sqlite3.connect(cls._db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM process WHERE is_started = 1")
            count = cursor.fetchone()[0]
            conn.close()
            return count > 0
        except Exception:
            return False

    @staticmethod
    def start_process():
        """Süreci başlatır"""
        return {
            'success': True,
            'output': 'Süreç başlatıldı',
            'error': None
        }

    @staticmethod
    def stop_process():
        """Süreci durdurur"""
        return {
            'success': True,
            'output': 'Süreç durduruldu',
            'error': None
        }

    @classmethod
    def check_process_started(cls):
        """Sürecin başlatılıp başlatılmadığını kontrol eder"""
        if not cls._check_db_process_status():
            return {
                'success': False,
                'output': None,
                'error': 'Süreç başlatılmadan adımlar çalıştırılamaz. Lütfen önce süreci başlatın.'
            }
        return None

    @staticmethod
    def send_mail(variables):
        # Süreç kontrolü
        check_result = ProcessExecutor.check_process_started()
        if check_result:
            return check_result

        try:
            # COM nesnelerini başlat
            pythoncom.CoInitialize()
            
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
            
            try:
                # Outlook uygulamasına bağlan
                outlook = win32com.client.Dispatch('Outlook.Application')
                mail = outlook.CreateItem(0)  # 0 = Mail item
                
                # Alıcıları ayarla
                if isinstance(variables['to'], list):
                    mail.To = '; '.join(variables['to'])
                else:
                    mail.To = variables['to']
                
                # CC alıcıları ayarla (varsa)
                if variables.get('cc'):
                    if isinstance(variables['cc'], list):
                        mail.CC = '; '.join(variables['cc'])
                    else:
                        mail.CC = variables['cc']
                
                # Konu ve içeriği ayarla
                mail.Subject = variables['subject']
                mail.Body = variables['body']
                
                # Maili gönder
                mail.Send()
                
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
        finally:
            # COM nesnelerini temizle
            pythoncom.CoUninitialize()

    @staticmethod
    def execute_mail_check(start_date=None):
        # Süreç kontrolü
        check_result = ProcessExecutor.check_process_started()
        if check_result:
            return check_result

        try:
            # COM nesnelerini başlat
            pythoncom.CoInitialize()
            
            # Outlook uygulamasına bağlan
            outlook = win32com.client.Dispatch('Outlook.Application')
            namespace = outlook.GetNamespace('MAPI')
            inbox = namespace.GetDefaultFolder(6)  # 6 = Gelen Kutusu
            
            # Son 10 maili al
            messages = inbox.Items
            messages.Sort('[ReceivedTime]', True)  # En yeni mailler başta olacak
            
            # Tarih filtresi uygula
            if start_date:
                # Outlook'un anlayacağı formata çevir
                filter_date = start_date.strftime('%m/%d/%Y %H:%M %p')
                messages = messages.Restrict(f"[ReceivedTime] >= '{filter_date}'")
            
            mails = []
            count = 0
            
            for message in messages:
                if count >= 10:
                    break
                
                mails.append({
                    'subject': message.Subject,
                    'sender': message.SenderName,
                    'received': message.ReceivedTime.strftime('%Y-%m-%d %H:%M:%S'),
                    'body': message.Body[:200] + '...' if len(message.Body) > 200 else message.Body
                })
                count += 1
            
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
        finally:
            # COM nesnelerini temizle
            pythoncom.CoUninitialize()

    @staticmethod
    def execute_python_script(file_path, output_dir=None):
        # Süreç kontrolü
        check_result = ProcessExecutor.check_process_started()
        if check_result:
            return check_result

        try:
            # Dosya yolundaki tırnak işaretlerini kaldır ve yolu normalize et
            file_path = file_path.strip('"').strip("'")
            file_path = os.path.normpath(file_path)
            
            # Çıktı dizinini ayarla
            env = os.environ.copy()
            if output_dir:
                # Çıktı dizinini oluştur (eğer yoksa)
                os.makedirs(output_dir, exist_ok=True)
                env['OUTPUT_DIR'] = output_dir
                
                # Script çalıştırılmadan önce dizindeki dosyaları kaydet
                ProcessExecutor._files_before = set(os.listdir(output_dir))
            
            # Python scriptini çalıştır
            result = subprocess.run(['python', file_path], 
                                 capture_output=True, 
                                 text=True,
                                 check=True,
                                 env=env,
                                 cwd=output_dir if output_dir else None)  # Çalışma dizinini output_dir olarak ayarla
            
            # Çıktı dosyasını kontrol et
            output_file = None
            if output_dir and hasattr(ProcessExecutor, '_files_before'):
                # Script çalıştıktan sonra oluşturulan yeni dosyaları kontrol et
                files_after = set(os.listdir(output_dir))
                new_files = files_after - ProcessExecutor._files_before
                if new_files:
                    output_file = list(new_files)[0]  # İlk yeni dosyayı al
            
            return {
                'success': True,
                'output': result.stdout,
                'error': result.stderr,
                'output_file': output_file
            }
        except subprocess.CalledProcessError as e:
            return {
                'success': False,
                'output': e.stdout,
                'error': e.stderr
            }
        except Exception as e:
            return {
                'success': False,
                'output': None,
                'error': str(e)
            }

    @staticmethod
    def execute_excel_file(file_path):
        # Süreç kontrolü
        check_result = ProcessExecutor.check_process_started()
        if check_result:
            return check_result

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
        # Süreç kontrolü
        check_result = ProcessExecutor.check_process_started()
        if check_result:
            return check_result

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
        # Süreç kontrolü
        check_result = ProcessExecutor.check_process_started()
        if check_result:
            return check_result

        if step_type == 'python_script':
            # Python script çalıştırılmadan önce çıktı dizinindeki dosyaları kaydet
            output_dir = kwargs.get('output_dir')
            if output_dir:
                ProcessExecutor._files_before = set(os.listdir(output_dir))
            return ProcessExecutor.execute_python_script(file_path, output_dir)
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
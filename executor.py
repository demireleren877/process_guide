import subprocess
import os
import pandas as pd
import sqlite3
import json
from datetime import datetime
import win32com.client
import pythoncom
import cx_Oracle

class ProcessExecutor:
    _instance = None
    _db_path = None  
    _oracle_config = {
        'username': None,
        'password': None,
        'dsn': None
    }
    
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
    def set_oracle_config(cls, username, password, dsn):
        cls._oracle_config = {
            'username': username,
            'password': password,
            'dsn': dsn
        }

    @classmethod
    def get_oracle_connection(cls):
        if not all(cls._oracle_config.values()):
            raise ValueError("Oracle bağlantı bilgileri eksik")
        return cx_Oracle.connect(
            cls._oracle_config['username'],
            cls._oracle_config['password'],
            cls._oracle_config['dsn']
        )

    @classmethod
    def _check_db_process_status(cls):
        """Veritabanından süreç durumunu kontrol et"""
        try:
            # Oracle bağlantısı oluştur
            conn = ProcessExecutor.get_oracle_connection()
            cursor = conn.cursor()
            
            # Süreç durumunu kontrol et
            cursor.execute("SELECT COUNT(*) FROM process WHERE is_started = 1")
            count = cursor.fetchone()[0]
            
            cursor.close()
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
        check_result = ProcessExecutor.check_process_started()
        if check_result:
            return check_result
        try:            
            pythoncom.CoInitialize()      
            if not variables:
                raise Exception('Mail konfigürasyonu bulunamadı')   
            if not variables.get('to'):
                raise Exception('En az bir alıcı belirtilmeli')
            if not variables.get('subject'):
                raise Exception('Mail konusu belirtilmeli')
            if not variables.get('body'):
                raise Exception('Mail içeriği belirtilmeli')       
            if not variables.get('active', False):
                return {
                    'success': True,
                    'output': 'Mail gönderimi pasif durumda',
                    'error': None
                }            
            try:                
                outlook = win32com.client.Dispatch('Outlook.Application')
                mail = outlook.CreateItem(0)                  
                if isinstance(variables['to'], list):
                    mail.To = '; '.join(variables['to'])
                else:
                    mail.To = variables['to']     
                if variables.get('cc'):
                    if isinstance(variables['cc'], list):
                        mail.CC = '; '.join(variables['cc'])
                    else:
                        mail.CC = variables['cc']           
                mail.Subject = variables['subject']
                mail.Body = variables['body']      
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
            pythoncom.CoUninitialize()

    @staticmethod
    def execute_mail_check(start_date=None, sent_at=None):        
        check_result = ProcessExecutor.check_process_started()
        if check_result:
            return check_result
        try:            
            pythoncom.CoInitialize()           
            outlook = win32com.client.Dispatch('Outlook.Application')
            namespace = outlook.GetNamespace('MAPI')
            inbox = namespace.GetDefaultFolder(6)  
            messages = inbox.Items
            messages.Sort('[ReceivedTime]', True)         
            filter_conditions = []
            if start_date:                
                filter_date = start_date.strftime('%m/%d/%Y %H:%M %p')
                filter_conditions.append(f"[ReceivedTime] >= '{filter_date}'")            
            if sent_at:                
                sent_date = sent_at.strftime('%m/%d/%Y %H:%M %p')
                filter_conditions.append(f"[ReceivedTime] >= '{sent_date}'")            
            if filter_conditions:
                messages = messages.Restrict(" AND ".join(filter_conditions))            
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
            pythoncom.CoUninitialize()

    @staticmethod
    def execute_python_script(file_path, output_dir=None,variables=None):        
        check_result = ProcessExecutor.check_process_started()
        if check_result:
            return check_result
        var_list = []
        for variable in variables:            
            var_list.append({"id":variable.name,"default_value":variable.default_value})
        variables = json.dumps(var_list)
        try:            
            file_path = file_path.strip('"').strip("'")
            file_path = os.path.normpath(file_path)       
            env = os.environ.copy()
            if output_dir:                
                os.makedirs(output_dir, exist_ok=True)
                env['OUTPUT_DIR'] = output_dir           
                ProcessExecutor._files_before = set(os.listdir(output_dir))            
            result = subprocess.run(['python', file_path], 
                                 capture_output=True, 
                                 text=True,
                                 check=True,
                                 input=variables,
                                 env=env,
                                 cwd=output_dir if output_dir else None)       
            output_file = None
            if output_dir and hasattr(ProcessExecutor, '_files_before'):                
                files_after = set(os.listdir(output_dir))
                new_files = files_after - ProcessExecutor._files_before
                if new_files:
                    output_file = list(new_files)[0]              
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
    def execute_sql_script(file_path, is_procedure=False, procedure_params=None):        
        check_result = ProcessExecutor.check_process_started()
        if check_result:
            return check_result
        try:            
            with open(file_path, 'r') as file:
                sql_script = file.read()
            conn = ProcessExecutor.get_oracle_connection()
            cursor = conn.cursor()
            
            try:
                if is_procedure:
                    if not procedure_params:
                        procedure_params = []
                    cursor.callproc(sql_script, procedure_params)
                    conn.commit()
                    return {
                        'success': True,
                        'output': "Oracle prosedürü başarıyla çalıştırıldı",
                        'error': None
                    }
                else:
                    if ';' in sql_script:
                        sql_script = f"BEGIN\n{sql_script}\nEND;"
                    cursor.execute(sql_script)
                    conn.commit()
                    return {
                        'success': True,
                        'output': "Oracle SQL script başarıyla çalıştırıldı",
                        'error': None
                    }
            except cx_Oracle.Error as error:
                return {
                    'success': False,
                    'output': None,
                    'error': f"Oracle hatası: {str(error)}"
                }
            finally:
                cursor.close()
                conn.close()
                
        except Exception as e:
            return {
                'success': False,
                'output': None,
                'error': str(e)
            }

    @staticmethod
    def execute_step(step_type, file_path, **kwargs):        
        check_result = ProcessExecutor.check_process_started()
        if check_result:
            return check_result
        if step_type == 'python_script':            
            output_dir = kwargs.get('output_dir')
            if output_dir:
                ProcessExecutor._files_before = set(os.listdir(output_dir))
            return ProcessExecutor.execute_python_script(file_path, output_dir,kwargs.get('variables'))
        elif step_type == 'sql_script':
            return ProcessExecutor.execute_sql_script(file_path, is_procedure=False)
        elif step_type == 'sql_procedure':
            procedure_params = kwargs.get('procedure_params', [])
            return ProcessExecutor.execute_sql_script(file_path, is_procedure=True, procedure_params=procedure_params)
        elif step_type == 'mail':
            if kwargs.get('variables'):                
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